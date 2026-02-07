"""Network Monitor TUI — live ping dashboard with Rich."""

import argparse
import platform
import re
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

PING_INTERVAL = float(__import__("os").environ.get("PING_INTERVAL", "1.0"))
WINDOW_SIZE = int(__import__("os").environ.get("WINDOW_SIZE", "30"))
REFRESH_RATE = float(__import__("os").environ.get("REFRESH_RATE", "0.8"))
PAGE_SIZE = int(__import__("os").environ.get("PAGE_SIZE", "100"))
SSH_CHECK_INTERVAL = float(__import__("os").environ.get("SSH_CHECK_INTERVAL", "600.0"))
SSH_PORT = int(__import__("os").environ.get("SSH_PORT", "22"))
SSH_CONNECT_TIMEOUT = 2

# Ping command: Windows uses -n 1 -w ms; Linux/macOS uses -c 1 -W seconds
IS_WINDOWS = platform.system().lower() == "windows"
PING_COUNT = "-n" if IS_WINDOWS else "-c"
PING_TIMEOUT = "-w" if IS_WINDOWS else "-W"
PING_TIMEOUT_VAL = "1000" if IS_WINDOWS else "1"

IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)
HOSTNAME_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)


def validate_target(value: str) -> Optional[str]:
    """Return stripped target if valid IP or hostname, else None."""
    s = value.strip()
    if not s or len(s) > 253:
        return None
    if IPV4_RE.match(s) or HOSTNAME_RE.match(s):
        return s
    return None


def parse_targets(raw: str) -> list[str]:
    """Parse comma-separated targets and return validated list."""
    return [t for part in raw.split(",") if (t := validate_target(part))]


def make_stats():
    return {
        "history": deque(maxlen=WINDOW_SIZE),
        "latency": 0,
        "status": "DOWN",
        "ssh": "—",
    }


stats: dict[str, dict] = {}
lock = threading.Lock()
stop_event = threading.Event()
filter_query: str = ""
filter_lock = threading.Lock()
status_filter: str = "all"
current_page: int = 1
current_ping_interval: list[float] = [PING_INTERVAL]
INTERVAL_PRESETS: list[float] = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0]


def ping_worker(target: str, _initial_interval: float) -> None:
    cmd = ["ping", PING_COUNT, "1", PING_TIMEOUT, PING_TIMEOUT_VAL, target]
    while not stop_event.is_set():
        interval = current_ping_interval[0]
        start = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=interval + 2,
            )
        except subprocess.TimeoutExpired:
            result = None
        except Exception:
            result = None
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        with lock:
            if target not in stats:
                break
            out = (result.stdout or "") if result else ""
            success = (
                result
                and result.returncode == 0
                and (
                    "Reply from" in out
                    or "bytes from" in out
                    or "received" in out
                    or "ttl=" in out.lower()
                )
            )
            if success:
                stats[target]["history"].append(1)
                stats[target]["latency"] = elapsed_ms
            else:
                stats[target]["history"].append(0)
                stats[target]["latency"] = 0
            hist = list(stats[target]["history"])
            stats[target]["status"] = "UP" if sum(hist[-3:]) >= 2 else "DOWN"

        deadline = time.perf_counter() + interval
        while time.perf_counter() < deadline and not stop_event.is_set():
            time.sleep(0.1)


def ssh_check_one(target: str, port: int, timeout: float) -> bool:
    """Try TCP connect to port; return True if connection succeeded."""
    try:
        sock = socket.create_connection((target, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def ssh_checker_worker(targets: list[str], interval: float, port: int) -> None:
    """Loop through targets periodically; update stats['ssh'] for each. Runs on its own interval."""
    while not stop_event.is_set():
        for target in targets:
            if stop_event.is_set():
                break
            with lock:
                if target not in stats:
                    continue
            ok = ssh_check_one(target, port, SSH_CONNECT_TIMEOUT)
            with lock:
                if target in stats:
                    stats[target]["ssh"] = "OK" if ok else "NO"
            time.sleep(0.2)
        deadline = time.perf_counter() + interval
        while time.perf_counter() < deadline and not stop_event.is_set():
            time.sleep(0.5)


def uptime_bar(ratio: float, width: int = 10) -> str:
    """Uptime bar: bracket style with color by range (green / yellow / red)."""
    filled = min(int(round(ratio * width / 100)), width)
    empty = width - filled
    if ratio <= 0:
        color = "dim"
    elif ratio >= 80:
        color = "green"
    elif ratio >= 50:
        color = "yellow1"
    else:
        color = "red1"
    bar_fill = "▮" * filled
    bar_empty = "▯" * empty
    return f"[{color}][{bar_fill}{bar_empty}][/{color}]"


def apply_filter(
    all_targets: list[str],
    query: str,
    status: str,
) -> list[str]:
    """
    Apply text filter (substring). Query can be multiple terms separated by comma or space; match any.
    status: "all" | "up" | "down"
    """
    if query and query.strip():
        terms = [p.strip().lower() for p in re.split(r"[,\s]+", query.strip()) if p.strip()]
        if terms:
            targets = [t for t in all_targets if any(term in t.lower() for term in terms)]
        else:
            targets = list(all_targets)
    else:
        targets = list(all_targets)
    if status == "all":
        return targets
    with lock:
        if status == "up":
            return [
                t for t in targets
                if stats.get(t, {}).get("status") == "UP"
                and stats.get(t, {}).get("ssh") == "OK"
            ]
        if status == "down":
            return [
                t for t in targets
                if stats.get(t, {}).get("status") == "DOWN"
                or stats.get(t, {}).get("ssh") == "NO"
            ]
    return targets


def build_header(
    target_list: list[str],
    all_targets: list[str],
    filter_str: str,
    status_filter_val: str,
    total_filtered: int,
    page: int,
    total_pages: int,
    page_size: int,
) -> Panel:
    with lock:
        total_online = sum(1 for ip in all_targets if stats.get(ip, {}).get("status") == "UP")
        total_offline = len(all_targets) - total_online
        ssh_unreachable = sum(1 for ip in all_targets if stats.get(ip, {}).get("ssh") != "OK")
    total = len(all_targets)
    shown = len(target_list)
    filter_info = ""
    if filter_str.strip():
        filter_info = f"  |  [yellow]Filter:[/] [bold]{filter_str.strip()}[/]  [dim]({shown}/{total})[/]"
    status_info = ""
    if status_filter_val == "up":
        status_info = "  |  [green]Status: UP + SSH OK[/]"
    elif status_filter_val == "down":
        status_info = "  |  [red]Status: DOWN or no SSH[/]"
    start_one = (page - 1) * page_size + 1 if total_filtered else 0
    end_one = min(page * page_size, total_filtered) if total_filtered else 0
    page_info = f"  |  [bold cyan]Page[/] {page}/{total_pages}  [dim]Targets {start_one}-{end_one} of {total_filtered}[/]"
    nav_hint = "  |  [dim]← → prev/next  Home/End first/last[/]"
    return Panel(
        f"[bold white]TOTAL:[/] {total}  |  "
        f"[bold green]Total online:[/] {total_online}  |  "
        f"[bold red]Total offline:[/] {total_offline}  |  "
        f"[bold]No SSH:[/] [red]{ssh_unreachable}[/]  |  "
        f"[dim]Interval: {current_ping_interval[0]}s  Window: {WINDOW_SIZE}[/]"
        f"{filter_info}{status_info}{page_info}{nav_hint}"
        f"  |  [dim]Esc=clear  u=UP d=DOWN a=all  i=interval  filter: comma/space = multiple[/]",
        style="cyan",
        border_style="bright_blue",
    )


def build_table(target_list: list[str]) -> Table:
    table = Table(
        header_style="bold magenta",
        expand=True,
        box=None,
        padding=(0, 1),
    )
    table.add_column("TARGET", ratio=1.5, style="white")
    table.add_column("ST", justify="center", ratio=0.4)
    table.add_column("REACHABILITY", justify="center", ratio=1.2)
    table.add_column("SSH", justify="center", ratio=0.5)
    table.add_column("MS", justify="right", ratio=0.5)
    table.add_column("UPTIME", ratio=1.5)
    table.add_column("%", justify="right", ratio=0.5)

    with lock:
        for target in target_list:
            data = stats.get(target, make_stats())
            history = list(data["history"])
            uptime = (sum(history) / len(history) * 100) if history else 0.0
            if data["status"] == "UP":
                status = "[bold green]UP[/]"
                reach = "[green]Reachable[/]"
            else:
                status = "[bold red]DN[/]"
                reach = "[red]Unreachable[/]"
            ssh_val = data.get("ssh", "—")
            if ssh_val == "OK":
                ssh_cell = "[bold green]OK[/]"
            elif ssh_val == "NO":
                ssh_cell = "[red]NO[/]"
            else:
                ssh_cell = "[dim]—[/]"
            table.add_row(
                target,
                status,
                reach,
                ssh_cell,
                str(data["latency"]),
                uptime_bar(uptime),
                f"{uptime:.0f}%",
            )
    return table


def build_layout(
    all_targets: list[str],
    filter_str: str,
    status_filter_val: str,
    page: int,
    page_size: int,
) -> Layout:
    """Build layout with text + reachability filter + pagination."""
    filtered = apply_filter(all_targets, filter_str, status_filter_val)
    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    page_targets = filtered[start : start + page_size]
    mid = (len(page_targets) + 1) // 2
    left = page_targets[:mid]
    right = page_targets[mid:]

    root = Layout()
    root.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    root["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    root["header"].update(
        build_header(
            page_targets,
            all_targets,
            filter_str,
            status_filter_val,
            total_filtered,
            page,
            total_pages,
            page_size,
        )
    )
    if not filtered:
        reason = []
        if filter_str.strip():
            reason.append(f"text filter '{filter_str.strip()}'")
        if status_filter_val != "all":
            reason.append(f"status={status_filter_val}")
        msg = "No targets match " + " and ".join(reason) if reason else "No targets"
        root["left"].update(
            Panel(
                Text.from_markup(f"[dim]{msg}[/]"),
                title="Filter",
            )
        )
        root["right"].update(Panel(""))
    else:
        root["left"].update(build_table(left))
        root["right"].update(build_table(right))
    return root


def main() -> None:
    global PING_INTERVAL, WINDOW_SIZE, REFRESH_RATE
    parser = argparse.ArgumentParser(
        description="Network Monitor TUI — live ping dashboard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="IP addresses or hostnames (comma-separated in one arg or multiple args)",
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=PING_INTERVAL,
        help="Ping interval in seconds",
    )
    parser.add_argument(
        "-w", "--window",
        type=int,
        default=WINDOW_SIZE,
        help="Sliding window size for uptime %%",
    )
    parser.add_argument(
        "-r", "--refresh",
        type=float,
        default=REFRESH_RATE,
        help="UI refresh interval in seconds",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt for IPs if none given (exit instead)",
    )
    parser.add_argument(
        "-f", "--filter",
        type=str,
        default="",
        help="Filter targets by substring (e.g. -f 8.8 or -f google). Empty = show all.",
    )
    parser.add_argument(
        "-s", "--status",
        type=str,
        choices=("all", "up", "down"),
        default="all",
        help="Filter by reachability: all (default), up (reachable only), down (unreachable only).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=PAGE_SIZE,
        metavar="N",
        help="Targets per page. Default 100. Use ←/→ (Windows) to change page.",
    )
    parser.add_argument(
        "--ssh-interval",
        type=float,
        default=SSH_CHECK_INTERVAL,
        metavar="SEC",
        help="SSH port check cycle interval (seconds). Default 600 (10 min).",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=SSH_PORT,
        metavar="PORT",
        help="TCP port for SSH check (default 22).",
    )
    args = parser.parse_args()

    raw = ",".join(args.targets) if args.targets else ""
    if not raw and not args.no_prompt:
        console.print("[bold cyan]NETWORK MONITOR[/bold cyan]")
        raw = console.input("Enter IP addresses or hostnames (comma separated): ")
    targets = parse_targets(raw)
    if not targets:
        console.print("[red]No valid targets. Enter IPs or hostnames (e.g. 8.8.8.8, google.com).[/red]")
        sys.exit(1)

    PING_INTERVAL = args.interval
    current_ping_interval[0] = PING_INTERVAL
    WINDOW_SIZE = args.window
    REFRESH_RATE = args.refresh
    page_size = max(1, args.page_size)
    ssh_interval = max(5.0, args.ssh_interval)
    ssh_port = max(1, min(65535, args.ssh_port))

    global filter_query, status_filter, current_page
    with filter_lock:
        filter_query = (args.filter or "").strip()
        status_filter = args.status
        current_page = 1

    for t in targets:
        stats[t] = make_stats()

    threads = [
        threading.Thread(target=ping_worker, args=(t, PING_INTERVAL), daemon=True)
        for t in targets
    ]
    for t in threads:
        t.start()

    # SSH checker: single thread, own interval (lightweight)
    ssh_thread = threading.Thread(
        target=ssh_checker_worker,
        args=(targets, ssh_interval, ssh_port),
        daemon=True,
    )
    ssh_thread.start()

    def keyboard_filter_thread() -> None:
        global filter_query, status_filter, current_page
        if not IS_WINDOWS:
            return
        try:
            import msvcrt
            while not stop_event.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch == b"\x1b":
                        with filter_lock:
                            filter_query = ""
                            current_page = 1
                        continue
                    if ch == b"\xe0":
                        if msvcrt.kbhit():
                            key2 = msvcrt.getch()
                            with filter_lock:
                                if key2 == b"\x4b":
                                    current_page = max(1, current_page - 1)
                                elif key2 == b"\x4d":
                                    current_page += 1
                                elif key2 == b"\x49":
                                    current_page = max(1, current_page - 1)
                                elif key2 == b"\x51":
                                    current_page += 1
                                elif key2 == b"\x47":
                                    current_page = 1
                                elif key2 == b"\x4f":
                                    current_page = 9999
                        continue
                    if ch == b"\x08":
                        with filter_lock:
                            filter_query = filter_query[:-1]
                        continue
                    try:
                        char = ch.decode("utf-8", errors="replace")
                        char_lower = char.lower()
                        if char_lower == "u":
                            with filter_lock:
                                status_filter = "up"
                                current_page = 1
                            continue
                        if char_lower == "d":
                            with filter_lock:
                                status_filter = "down"
                                current_page = 1
                            continue
                        if char_lower == "a":
                            with filter_lock:
                                status_filter = "all"
                                current_page = 1
                            continue
                        if char_lower == "i":
                            idx = next(
                                (i for i, p in enumerate(INTERVAL_PRESETS) if p >= current_ping_interval[0]),
                                0,
                            )
                            current_ping_interval[0] = INTERVAL_PRESETS[(idx + 1) % len(INTERVAL_PRESETS)]
                            continue
                        if char.isprintable():
                            with filter_lock:
                                filter_query += char
                                current_page = 1
                    except Exception:
                        pass
                time.sleep(0.05)
        except Exception:
            pass

    kbd_thread = threading.Thread(target=keyboard_filter_thread, daemon=True)
    kbd_thread.start()

    def get_filter_state() -> tuple[str, str, int]:
        with filter_lock:
            return filter_query, status_filter, current_page

    try:
        fq, sf, cp = get_filter_state()
        with Live(
            build_layout(targets, fq, sf, cp, page_size),
            refresh_per_second=1 / REFRESH_RATE,
            screen=True,
            console=console,
        ) as live:
            while True:
                fq, sf, cp = get_filter_state()
                live.update(build_layout(targets, fq, sf, cp, page_size))
                time.sleep(REFRESH_RATE)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=PING_INTERVAL * 2)
        ssh_thread.join(timeout=ssh_interval + 5)
    console.print("[dim]Stopped.[/dim]")


if __name__ == "__main__":
    main()

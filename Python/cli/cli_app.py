"""
Interactive High-Performance Rich CLI for the Download Manager.
Features:
- Live multi-segment visualizer with individual chunk blocks.
- Real-time animated speed, ETA, and progress metrics.
- Subcommands: download, list, pause, resume, cancel, status, monitor.
"""

from __future__ import annotations
import sys
import os
import time
import argparse
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    SpinnerColumn
)
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

# Ensure core can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.queue_manager import QueueManager
from core.models import DownloadStatus, DownloadCategory, DownloadTask, format_eta
from core.prober import probe_url


def format_bytes(size_bytes: float) -> str:
    """Formats bytes into human readable string (KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


def render_segment_blocks(task: DownloadTask, width: int = 40) -> Text:
    """Renders a visual string of colored blocks representing individual segments."""
    if not task.segments or task.total_bytes <= 0:
        pct = int(task.progress_pct)
        filled = int(width * (pct / 100.0))
        return Text("█" * filled + "░" * (width - filled), style="green" if task.status == DownloadStatus.COMPLETED else "cyan")

    text = Text()
    for seg in task.segments:
        ratio = seg.downloaded_bytes / max(1, seg.total_bytes)
        seg_width = max(1, int(width * (seg.total_bytes / task.total_bytes)))
        filled = int(seg_width * ratio)
        empty = seg_width - filled

        if seg.status == "COMPLETED":
            text.append("█" * seg_width, style="bright_green")
        elif seg.status == "DOWNLOADING":
            text.append("█" * filled, style="bright_cyan")
            text.append("▒" * empty, style="dim cyan")
        elif seg.status == "ERROR":
            text.append("█" * filled, style="bright_red")
            text.append("░" * empty, style="dim red")
        else:
            text.append("░" * seg_width, style="dim white")

    return text


class CLIApp:
    def __init__(self):
        self.console = Console(force_terminal=True)
        self.qm = QueueManager()

    def run_single_download(
        self,
        url: str,
        connections: int = 16,
        output: Optional[str] = None,
        filename: Optional[str] = None,
        checksum: Optional[str] = None,
        algo: Optional[str] = None,
        leech_only: bool = True,
        sequential: bool = False,
        max_peers: int = 100
    ) -> None:
        """Downloads a URL, magnet link, or .torrent synchronously in the foreground with a rich live visualizer."""
        self.console.print(Panel(f"[bold cyan]Turbo Download Manager[/bold cyan]\n[dim]Target: {url}[/dim]", border_style="cyan"))

        self.console.print("[yellow]🔍 Probing resource and server capabilities...[/yellow]")
        probe = probe_url(url)
        
        self.console.print(f"[bold green]✓[/bold green] Filename: [bold]{filename or probe.filename}[/bold]")
        if probe.total_bytes > 0:
            self.console.print(f"[bold green]✓[/bold green] File Size: [bold]{format_bytes(probe.total_bytes)}[/bold]")
        if probe.is_torrent:
            self.console.print(f"[bold magenta]🧲 BitTorrent Swarm Detected[/bold magenta] [dim](Leech Only: {'Enabled' if leech_only else 'Disabled'}, Max Peers: {max_peers})[/dim]")
        elif probe.is_media_stream:
            self.console.print("[bold magenta]★ Media Stream Detected (Integrated Stream Extractor)[/bold magenta]")
        else:
            self.console.print(f"[bold green]✓[/bold green] Multipart Acceleration: [{'green' if probe.supports_range else 'yellow'}]{'Supported (' + str(connections) + ' connections)' if probe.supports_range else 'Single Stream'}[/{'green' if probe.supports_range else 'yellow'}]")
        
        if checksum:
            self.console.print(f"[bold green]✓[/bold green] Integrity Checksum: [cyan]{checksum}[/cyan] ({algo or 'sha256'})")

        task = self.qm.create_and_add_task(
            url=url,
            save_path=output or self.qm.settings.default_save_dir,
            filename=filename or probe.filename,
            num_connections=connections,
            expected_checksum=checksum,
            checksum_algo=algo.lower() if algo else ("sha256" if checksum else None),
            auto_start=True,
            is_torrent=probe.is_torrent,
            leech_only=leech_only,
            sequential_download=sequential,
            max_peers=max_peers
        )

        with Live(console=self.console, refresh_per_second=4) as live:
            while task.status in (DownloadStatus.QUEUED, DownloadStatus.CONNECTING, DownloadStatus.DOWNLOADING):
                time.sleep(0.25)
                # Build live status panel
                grid = Table.grid(expand=True)
                grid.add_column(justify="left")
                grid.add_column(justify="right")

                speed_str = f"{format_bytes(task.speed_bytes_per_sec)}/s"
                eta_str = format_eta(task.eta_seconds)
                transferred = f"{format_bytes(task.downloaded_bytes)} / {format_bytes(task.total_bytes)}"
                pct_str = f"{task.progress_pct:.1f}%"

                grid.add_row(
                    Text(f"File: {task.filename}", style="bold white"),
                    Text(f"Status: {task.status.value}", style="bold yellow" if task.status == DownloadStatus.CONNECTING else "bold cyan")
                )
                grid.add_row(
                    Text(f"Speed: {speed_str} | ETA: {eta_str}", style="green"),
                    Text(f"{transferred} ({pct_str})", style="bold magenta")
                )

                # Segment visualization
                seg_blocks = render_segment_blocks(task, width=50)

                # Segment table if multiple segments exist
                body = Table(show_header=True, header_style="bold dim cyan", box=box.SIMPLE)
                body.add_column("Segment", justify="center", width=8)
                body.add_column("Range", width=25)
                body.add_column("Downloaded", justify="right", width=15)
                body.add_column("Status", width=12)

                if task.segments:
                    for s in task.segments[:12]:  # Show top 12 segments
                        body.add_row(
                            f"#{s.segment_id + 1}",
                            f"{format_bytes(s.start_byte)} - {format_bytes(s.end_byte)}",
                            f"{format_bytes(s.downloaded_bytes)} ({s.progress_pct:.0f}%)",
                            f"[{'green' if s.status == 'COMPLETED' else 'cyan' if s.status == 'DOWNLOADING' else 'dim'}]{s.status}[/]"
                        )
                    if len(task.segments) > 12:
                        body.add_row("...", "...", f"+{len(task.segments)-12} more segments", "...")

                panel_content = Table.grid(expand=True)
                panel_content.add_row(grid)
                panel_content.add_row(Text(""))
                panel_content.add_row(seg_blocks)
                if task.segments:
                    panel_content.add_row(Text(""))
                    panel_content.add_row(body)

                live.update(Panel(panel_content, title="[bold cyan]Downloading...[/bold cyan]", border_style="cyan"))

            # Final state display
            if task.status == DownloadStatus.COMPLETED:
                live.update(Panel(
                    f"[bold green]✓ Download Completed Successfully![/bold green]\n\n"
                    f"Saved to: [bold]{task.full_output_path}[/bold]\n"
                    f"Total Size: [bold]{format_bytes(task.downloaded_bytes)}[/bold]",
                    border_style="green"
                ))
            elif task.status == DownloadStatus.ERROR:
                live.update(Panel(
                    f"[bold red]✗ Download Failed![/bold red]\n\nError: {task.error_message}",
                    border_style="red"
                ))

    def list_tasks(self) -> None:
        """Prints a rich table of all download tasks."""
        tasks = self.qm.get_all_tasks()
        if not tasks:
            self.console.print("[dim]No download tasks found in history.[/dim]")
            return

        table = Table(title="Downloads History & Queue", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Filename", style="bold white", max_width=30)
        table.add_column("Size", justify="right", width=12)
        table.add_column("Progress", justify="center", width=20)
        table.add_column("Speed", justify="right", width=12)
        table.add_column("Status", width=12)
        table.add_column("Category", width=12)

        for t in tasks:
            status_style = {
                DownloadStatus.COMPLETED: "green",
                DownloadStatus.DOWNLOADING: "cyan",
                DownloadStatus.PAUSED: "yellow",
                DownloadStatus.ERROR: "red",
                DownloadStatus.QUEUED: "dim white",
                DownloadStatus.CANCELLED: "dim red",
                DownloadStatus.CONNECTING: "bold yellow"
            }.get(t.status, "white")

            pct = t.progress_pct
            bar_len = 10
            filled = int(bar_len * (pct / 100.0))
            prog_bar = f"[{'green' if t.status == DownloadStatus.COMPLETED else 'cyan'}]{'█'*filled}{'░'*(bar_len-filled)}[/] {pct:.0f}%"

            speed_str = f"{format_bytes(t.speed_bytes_per_sec)}/s" if t.status == DownloadStatus.DOWNLOADING else "-"

            table.add_row(
                t.task_id,
                t.filename or "Unknown",
                format_bytes(t.total_bytes),
                prog_bar,
                speed_str,
                f"[{status_style}]{t.status.value}[/{status_style}]",
                t.category.value
            )

        self.console.print(table)

    def pause_task(self, task_id: str) -> None:
        if self.qm.pause_task(task_id):
            self.console.print(f"[bold yellow]Paused task {task_id}[/bold yellow]")
        else:
            self.console.print(f"[red]Task {task_id} not found.[/red]")

    def resume_task(self, task_id: str) -> None:
        if self.qm.start_task(task_id):
            self.console.print(f"[bold green]Resumed task {task_id}[/bold green]")
        else:
            self.console.print(f"[red]Task {task_id} not found.[/red]")

    def cancel_task(self, task_id: str) -> None:
        if self.qm.cancel_task(task_id):
            self.console.print(f"[bold red]Cancelled task {task_id}[/bold red]")
        else:
            self.console.print(f"[red]Task {task_id} not found.[/red]")

    def show_status(self, task_id: str) -> None:
        task = self.qm.get_task(task_id)
        if not task:
            self.console.print(f"[red]Task {task_id} not found.[/red]")
            return

        grid = Table.grid(padding=1)
        grid.add_column(style="bold cyan", width=15)
        grid.add_column()

        grid.add_row("Task ID:", task.task_id)
        grid.add_row("URL:", task.url)
        grid.add_row("Filename:", task.filename)
        grid.add_row("Destination:", task.full_output_path)
        grid.add_row("Total Size:", format_bytes(task.total_bytes))
        grid.add_row("Downloaded:", f"{format_bytes(task.downloaded_bytes)} ({task.progress_pct:.2f}%)")
        grid.add_row("Status:", task.status.value)
        grid.add_row("Acceleration:", f"{task.num_connections} connections" if task.supports_range else "Single stream")
        grid.add_row("Category:", task.category.value)
        if task.error_message:
            grid.add_row("Error:", f"[red]{task.error_message}[/red]")

        self.console.print(Panel(grid, title=f"Task Details [{task.task_id}]", border_style="cyan"))

    def batch_download(self, file_path_or_urls: str, connections: int = 16, output: Optional[str] = None) -> None:
        """Reads URLs from a file or comma-separated list and starts batch downloading."""
        urls = []
        if os.path.isfile(file_path_or_urls):
            with open(file_path_or_urls, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and line.strip().startswith(("http://", "https://"))]
        else:
            urls = [u.strip() for u in file_path_or_urls.split(",") if u.strip().startswith(("http://", "https://"))]

        if not urls:
            self.console.print("[red]No valid URLs found to download.[/red]")
            return

        self.console.print(f"[bold cyan]Queueing {len(urls)} URLs for accelerated download...[/bold cyan]")
        tasks = self.qm.create_and_add_batch_tasks(
            urls=urls,
            save_path=output or self.qm.settings.default_save_dir,
            num_connections=connections,
            auto_start=True
        )
        self.console.print(f"[bold green]✓ Successfully added {len(tasks)} tasks to download queue.[/bold green]")
        self.list_tasks()

    def monitor_dashboard(self) -> None:
        """Renders an interactive live updating dashboard of all downloads."""
        self.console.print("[yellow]Starting Turbo Live Monitor... (Press Ctrl+C to exit)[/yellow]")
        try:
            with Live(console=self.console, refresh_per_second=2) as live:
                while True:
                    time.sleep(0.5)
                    tasks = self.qm.get_all_tasks()
                    total_speed = sum(t.speed_bytes_per_sec for t in tasks if t.status == DownloadStatus.DOWNLOADING)
                    active_cnt = sum(1 for t in tasks if t.status in (DownloadStatus.DOWNLOADING, DownloadStatus.CONNECTING))

                    table = Table(box=box.ROUNDED, header_style="bold cyan", expand=True)
                    table.add_column("ID", width=10, style="dim")
                    table.add_column("Filename", max_width=25, style="bold white")
                    table.add_column("Size", justify="right", width=10)
                    table.add_column("Progress", justify="center", width=25)
                    table.add_column("Speed", justify="right", width=12)
                    table.add_column("ETA", justify="right", width=14)
                    table.add_column("Status", width=12)

                    for t in tasks:
                        status_color = {
                            DownloadStatus.COMPLETED: "green",
                            DownloadStatus.DOWNLOADING: "cyan",
                            DownloadStatus.PAUSED: "yellow",
                            DownloadStatus.ERROR: "red",
                            DownloadStatus.QUEUED: "dim white",
                            DownloadStatus.CANCELLED: "dim red",
                            DownloadStatus.CONNECTING: "bold yellow"
                        }.get(t.status, "white")

                        pct = t.progress_pct
                        bar_len = 12
                        filled = int(bar_len * (pct / 100.0))
                        prog = f"[{'green' if t.status == DownloadStatus.COMPLETED else 'cyan'}]{'█'*filled}{'░'*(bar_len-filled)}[/] {pct:.0f}%"

                        speed = f"{format_bytes(t.speed_bytes_per_sec)}/s" if t.status == DownloadStatus.DOWNLOADING else "-"
                        eta = format_eta(t.eta_seconds) if t.status == DownloadStatus.DOWNLOADING else "-"

                        table.add_row(
                            t.task_id,
                            t.filename or "Unknown",
                            format_bytes(t.total_bytes),
                            prog,
                            speed,
                            eta,
                            f"[{status_color}]{t.status.value}[/{status_color}]"
                        )

                    header_panel = Panel(
                        f"⚡ [bold cyan]Total Speed:[/bold cyan] [bold green]{format_bytes(total_speed)}/s[/bold green] | "
                        f"Active: [bold]{active_cnt}/{self.qm.settings.max_concurrent_downloads}[/bold] | "
                        f"Total Downloads: [bold]{len(tasks)}[/bold]",
                        title="[bold cyan]Turbo Download Manager Dashboard[/bold cyan]",
                        border_style="cyan"
                    )

                    layout = Table.grid(expand=True)
                    layout.add_row(header_panel)
                    layout.add_row(table)

                    live.update(layout)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Exited Live Monitor.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Turbo Download Manager - High-Performance Multi-Connection CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # download command
    dl_parser = subparsers.add_parser("download", help="Download a URL, magnet link, or .torrent with multi-connection acceleration")
    dl_parser.add_argument("url", help="Target URL, magnet link, or .torrent to download")
    dl_parser.add_argument("-n", "--connections", type=int, default=16, help="Number of accelerated parallel connections (1-32)")
    dl_parser.add_argument("-o", "--output", help="Destination folder path")
    dl_parser.add_argument("-f", "--filename", help="Custom output filename")
    dl_parser.add_argument("-c", "--checksum", help="Expected hash for automatic integrity verification")
    dl_parser.add_argument("-a", "--algo", default="sha256", choices=["sha256", "md5", "sha1", "sha512"], help="Hash algorithm (default: sha256)")
    dl_parser.add_argument("--leech-only", action="store_true", default=True, help="Enable Leech Only mode (zero upload/seeding, stops on complete)")
    dl_parser.add_argument("--allow-upload", dest="leech_only", action="store_false", help="Allow uploading/seeding to peers in swarm")
    dl_parser.add_argument("--sequential", action="store_true", default=False, help="Download pieces in linear sequential order for video streaming")
    dl_parser.add_argument("--max-peers", type=int, default=100, help="Max peer connections for torrent swarm (default: 100)")

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Batch download URLs from a file or comma-separated list")
    batch_parser.add_argument("source", help="Path to text file containing URLs or comma-separated URLs")
    batch_parser.add_argument("-n", "--connections", type=int, default=16, help="Connections per download (1-32)")
    batch_parser.add_argument("-o", "--output", help="Destination folder path")

    # monitor command
    subparsers.add_parser("monitor", help="Open full-screen live updating terminal dashboard")

    # list command
    subparsers.add_parser("list", help="List all downloads and their statuses")

    # pause command
    pause_parser = subparsers.add_parser("pause", help="Pause a running download")
    pause_parser.add_argument("task_id", help="Task ID")

    # resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a paused download")
    resume_parser.add_argument("task_id", help="Task ID")

    # cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a download")
    cancel_parser.add_argument("task_id", help="Task ID")

    # status command
    status_parser = subparsers.add_parser("status", help="Show detailed task information")
    status_parser.add_argument("task_id", help="Task ID")

    args = parser.parse_args()
    app = CLIApp()

    if args.command == "download":
        app.run_single_download(
            args.url,
            connections=args.connections,
            output=args.output,
            filename=args.filename,
            checksum=args.checksum,
            algo=args.algo,
            leech_only=args.leech_only,
            sequential=args.sequential,
            max_peers=args.max_peers
        )
    elif args.command == "batch":
        app.batch_download(args.source, connections=args.connections, output=args.output)
    elif args.command == "monitor":
        app.monitor_dashboard()
    elif args.command == "list":
        app.list_tasks()
    elif args.command == "pause":
        app.pause_task(args.task_id)
    elif args.command == "resume":
        app.resume_task(args.task_id)
    elif args.command == "cancel":
        app.cancel_task(args.task_id)
    elif args.command == "status":
        app.show_status(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


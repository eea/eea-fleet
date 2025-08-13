"""
EEA Fleet Configuration Generator - Consolidated Screens Module

All UI screens consolidated into base classes with configuration-driven behavior.
Eliminates 20+ screen files and reduces duplication while maintaining functionality.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    TextArea,
    TabbedContent,
    TabPane,
    ProgressBar,
    Log,
    SelectionList,
    Checkbox,
    DirectoryTree,
)
from textual.binding import Binding

from typing import Dict, List, Optional, Callable, Tuple
from pathlib import Path
import asyncio
import json

import yaml
from . import core
from .models import FleetConfig, HELP_TEXT_CONTENT


# ==============================================================================
# BASE SCREEN CLASSES
# ==============================================================================


class BaseInputScreen(ModalScreen):
    """Generic input screen for various input scenarios."""

    CSS = """
    BaseInputScreen {
        align: center middle;
    }
    
    #input_container {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    #input_buttons {
        height: 3;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        title: str,
        fields: List[Dict],
        validation_callback: Optional[Callable] = None,
    ):
        super().__init__()
        self.modal_title = title
        self.fields = fields  # [{"name": "field_name", "label": "Label", "type": "text", "required": True}]
        self.validation_callback = validation_callback
        self.field_values = {}

    def compose(self) -> ComposeResult:
        with Container(id="input_container"):
            yield Label(self.modal_title, classes="input_title")

            for field in self.fields:
                yield Label(field["label"])
                if field["type"] == "text":
                    yield Input(
                        placeholder=field.get("placeholder", ""),
                        id=f"input_{field['name']}",
                    )
                elif field["type"] == "textarea":
                    yield TextArea(id=f"input_{field['name']}")
                elif field["type"] == "directory":
                    yield DirectoryTree(Path.cwd(), id=f"input_{field['name']}")

            with Horizontal(id="input_buttons"):
                yield Button("OK", variant="primary", id="ok_button")
                yield Button("Cancel", variant="default", id="cancel_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok_button":
            self.collect_values()
            if self.validate_inputs():
                self.dismiss(self.field_values)
        elif event.button.id == "cancel_button":
            self.dismiss(None)

    def collect_values(self):
        """Collect values from input fields."""
        for field in self.fields:
            field_id = f"input_{field['name']}"
            widget = self.query_one(f"#{field_id}")

            if field["type"] in ["text", "textarea"]:
                self.field_values[field["name"]] = widget.value
            elif field["type"] == "directory":
                self.field_values[field["name"]] = str(widget.path)

    def validate_inputs(self) -> bool:
        """Validate input values."""
        for field in self.fields:
            if field.get("required", False):
                value = self.field_values.get(field["name"], "")
                if not value or not str(value).strip():
                    self.notify(f"{field['label']} is required", severity="error")
                    return False

        if self.validation_callback:
            return self.validation_callback(self.field_values)

        return True


class BaseListScreen(Screen):
    """Generic list/selection screen with search and filters."""

    CSS = """
    BaseListScreen {
        layout: vertical;
    }
    
    #list_header {
        height: 3;
        background: $surface;
    }
    
    #search_container {
        height: 3;
        margin: 1 0;
    }
    
    #list_table {
        height: 1fr;
    }
    
    #list_actions {
        height: 3;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "search", "Search"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        title: str,
        data_service: Callable,
        columns: List[str],
        actions: List[Dict],
        selection_mode: str = "single",
    ):
        super().__init__()
        self.screen_title = title
        self.data_service = data_service
        self.columns = columns
        self.actions = actions  # [{"name": "action_name", "label": "Button Label", "callback": function}]
        self.selection_mode = selection_mode
        self.current_data = []
        self.selected_items = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="list_header"):
            yield Label(self.screen_title, classes="screen_title")

        with Container(id="search_container"):
            yield Input(placeholder="Search...", id="search_input")

        yield DataTable(
            id="list_table",
            cursor_type="row" if self.selection_mode == "single" else "cell",
        )

        with Horizontal(id="list_actions"):
            for action in self.actions:
                yield Button(action["label"], id=f"action_{action['name']}")
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize table and load data."""
        table = self.query_one("#list_table", DataTable)

        # Add columns
        for column in self.columns:
            table.add_column(column, key=column.lower().replace(" ", "_"))

        await self.refresh_data()

    async def refresh_data(self):
        """Refresh data from service."""
        try:
            self.current_data = await asyncio.to_thread(self.data_service)
            self.update_table()
        except Exception as e:
            self.notify(f"Error loading data: {str(e)}", severity="error")

    def update_table(self):
        """Update table with current data."""
        table = self.query_one("#list_table", DataTable)
        table.clear()

        for item in self.current_data:
            if isinstance(item, (list, tuple)):
                table.add_row(*item)
            elif isinstance(item, dict):
                row_data = [
                    str(item.get(col.lower().replace(" ", "_"), ""))
                    for col in self.columns
                ]
                table.add_row(*row_data)
            else:
                # Handle objects with attributes
                row_data = [
                    str(getattr(item, col.lower().replace(" ", "_"), ""))
                    for col in self.columns
                ]
                table.add_row(*row_data)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search_input":
            search_term = event.value.lower()
            if search_term:
                filtered_data = [
                    item
                    for item in self.current_data
                    if any(
                        search_term in str(getattr(item, attr, "")).lower()
                        for attr in dir(item)
                        if not attr.startswith("_")
                    )
                ]
                self.current_data = filtered_data
            else:
                asyncio.create_task(self.refresh_data())
            self.update_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if self.selection_mode == "single":
            # Use cursor_row instead of row_index for newer Textual versions
            row_idx = event.cursor_row
            self.selected_items = (
                [self.current_data[row_idx]] if row_idx < len(self.current_data) else []
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()
        else:
            for action in self.actions:
                if event.button.id == f"action_{action['name']}":
                    action["callback"](self.selected_items)
                    break

    def action_search(self) -> None:
        """Focus search input."""
        self.query_one("#search_input").focus()

    def action_refresh(self) -> None:
        """Refresh data."""
        asyncio.create_task(self.refresh_data())

    def action_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()


class ProcessScreen(Screen):
    """Generic process/progress screen for operations."""

    CSS = """
    ProcessScreen {
        layout: vertical;
    }
    
    #process_header {
        height: 5;
        background: $surface;
    }
    
    #progress_container {
        height: 5;
        margin: 1;
    }
    
    #log_container {
        height: 1fr;
        margin: 1;
    }
    
    #process_actions {
        height: 3;
        dock: bottom;
    }
    """

    def __init__(self, title: str, process_service: Callable, config: Dict):
        super().__init__()
        self.screen_title = title
        self.process_service = process_service
        self.config = config
        self.is_running = False

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="process_header"):
            yield Label(self.screen_title, classes="screen_title")
            yield Label("Ready to start process", id="status_label")

        with Container(id="progress_container"):
            yield Label("Progress:", id="progress_label")
            yield ProgressBar(id="progress_bar")

        with Container(id="log_container"):
            yield Label("Process Log:")
            yield Log(id="process_log")

        with Horizontal(id="process_actions"):
            yield Button("Start", variant="primary", id="start_button")
            yield Button("Stop", variant="error", id="stop_button", disabled=True)
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "start_button":
            await self.start_process()
        elif event.button.id == "stop_button":
            self.stop_process()
        elif event.button.id == "back_button":
            self.app.pop_screen()

    async def start_process(self):
        """Start the process."""
        self.is_running = True
        self.query_one("#start_button").disabled = True
        self.query_one("#stop_button").disabled = False
        self.query_one("#status_label").update("Process running...")

        log = self.query_one("#process_log", Log)
        progress = self.query_one("#progress_bar", ProgressBar)

        try:
            log.write_line(f"Starting {self.screen_title}...")

            # Run process service
            result = await asyncio.to_thread(
                self.process_service, self.config, self.update_progress
            )

            if result.get("success", False):
                log.write_line("Process completed successfully!")
                progress.progress = 100
                self.query_one("#status_label").update("Process completed")
                self.notify("Process completed successfully!", severity="success")
            else:
                error_msg = result.get("error", "Unknown error")
                log.write_line(f"Process failed: {error_msg}")
                self.query_one("#status_label").update("Process failed")
                self.notify(f"Process failed: {error_msg}", severity="error")

        except Exception as e:
            log.write_line(f"Process error: {str(e)}")
            self.query_one("#status_label").update("Process error")
            self.notify(f"Process error: {str(e)}", severity="error")
        finally:
            self.is_running = False
            self.query_one("#start_button").disabled = False
            self.query_one("#stop_button").disabled = True

    def update_progress(self, progress: int, message: str):
        """Update progress bar and log."""
        self.query_one("#progress_bar").progress = progress
        self.query_one("#process_log").write_line(message)

    def stop_process(self):
        """Stop the running process."""
        self.is_running = False
        self.query_one("#start_button").disabled = False
        self.query_one("#stop_button").disabled = True
        self.query_one("#status_label").update("Process stopped")
        self.query_one("#process_log").write_line("Process stopped by user")


class ViewScreen(Screen):
    """Generic content viewer with tabs."""

    CSS = """
    ViewScreen {
        layout: vertical;
    }
    
    #view_header {
        height: 3;
        background: $surface;
    }
    
    #view_content {
        height: 1fr;
    }
    
    #view_actions {
        height: 3;
        dock: bottom;
    }
    """

    def __init__(
        self, title: str, content_data: Dict[str, str], actions: List[Dict] = None
    ):
        super().__init__()
        self.screen_title = title
        self.content_data = content_data  # {"tab_name": "content"}
        self.actions = actions or []

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="view_header"):
            yield Label(self.screen_title, classes="screen_title")

        with TabbedContent(id="view_content"):
            for tab_name, content in self.content_data.items():
                with TabPane(tab_name, id=f"tab_{tab_name.lower().replace(' ', '_')}"):
                    yield TextArea(content, read_only=True)

        with Horizontal(id="view_actions"):
            for action in self.actions:
                yield Button(action["label"], id=f"action_{action['name']}")
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()
        else:
            for action in self.actions:
                if event.button.id == f"action_{action['name']}":
                    action["callback"](self.content_data)
                    break


# ==============================================================================
# SPECIALIZED SCREENS
# ==============================================================================


class MainScreen(Screen):
    """Main menu and navigation hub."""

    CSS = """
    MainScreen {
        layout: vertical;
        align: center middle;
    }
    
    #main_container {
        width: 80;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 2;
    }
    
    #main_title {
        text-align: center;
        margin-bottom: 2;
    }
    
    #main_menu {
        height: auto;
    }
    
    .menu_button {
        width: 100%;
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("h", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main_container"):
            yield Label(
                "🚀 EEA Fleet Configuration Generator", id="main_title", classes="title"
            )

            with Vertical(id="main_menu"):
                yield Button(
                    "🏗️  Setup Rancher Connection",
                    classes="menu_button",
                    id="setup_rancher",
                )
                yield Button(
                    "🚀 Generate Fleet Configuration",
                    classes="menu_button",
                    id="generate_config",
                )
                yield Button(
                    "📦 Browse EEA Charts", classes="menu_button", id="browse_charts"
                )
                yield Button(
                    "🔍 View Existing Configurations",
                    classes="menu_button",
                    id="view_configs",
                )
                yield Button(
                    "⚙️  Application Settings", classes="menu_button", id="app_settings"
                )
                yield Button("❓ Help", classes="menu_button", id="help_screen")
                yield Button("🚪 Quit", classes="menu_button", id="quit_app")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle main menu button presses."""
        if event.button.id == "setup_rancher":
            self.app.push_screen(RancherSetupScreen())
        elif event.button.id == "generate_config":
            self.app.push_screen(FleetConfigurationScreen())
        elif event.button.id == "browse_charts":
            self.app.push_screen(self.create_charts_list_screen())
        elif event.button.id == "view_configs":
            self.app.push_screen(self.create_existing_configs_screen())
        elif event.button.id == "app_settings":
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "help_screen":
            self.app.push_screen(HelpScreen())
        elif event.button.id == "quit_app":
            self.app.exit()

    def create_charts_list_screen(self) -> BaseListScreen:
        """Create charts list screen."""
        return BaseListScreen(
            title="EEA Helm Charts",
            data_service=lambda: core.create_chart_table_data(),
            columns=["Chart Name", "Category", "Description"],
            actions=[
                {
                    "name": "select",
                    "label": "Select Chart",
                    "callback": self.on_chart_selected,
                }
            ],
        )

    def create_existing_configs_screen(self) -> BaseListScreen:
        """Create existing configurations screen."""
        return BaseListScreen(
            title="Existing Fleet Configurations",
            data_service=self.load_existing_configs,
            columns=["App Name", "Chart", "Namespace", "Status"],
            actions=[
                {
                    "name": "view",
                    "label": "View Config",
                    "callback": self.on_config_view,
                },
                {
                    "name": "deploy",
                    "label": "Deploy",
                    "callback": self.on_config_deploy,
                },
            ],
        )

    def load_existing_configs(self) -> List[Tuple]:
        """Load existing configurations from cluster-organized structure."""
        configs = []
        apps_dir = core.get_apps_dir()
        if apps_dir.exists():
            # Scan cluster folders
            for cluster_dir in apps_dir.iterdir():
                if cluster_dir.is_dir():
                    cluster_name = cluster_dir.name
                    # Scan app directories within each cluster
                    for app_dir in cluster_dir.iterdir():
                        if app_dir.is_dir():
                            # Look for fleet.yaml files (the actual configuration files)
                            fleet_file = app_dir / "fleet.yaml"
                            if fleet_file.exists():
                                app_name = app_dir.name
                                # Parse namespace and chart from app_name format: <namespace>-<chart>
                                parts = app_name.split('-', 1)
                                namespace = parts[0] if len(parts) > 0 else "unknown"
                                chart_name = parts[1] if len(parts) > 1 else app_name
                                
                                configs.append(
                                    (
                                        f"{cluster_name}/{app_name}",  # Display cluster/app for clarity
                                        chart_name,
                                        namespace,
                                        cluster_name,  # Show cluster as status/target
                                    )
                                )
        return configs

    def on_chart_selected(self, selected_items):
        """Handle chart selection."""
        if selected_items:
            chart_name = (
                selected_items[0][0]
                if isinstance(selected_items[0], (list, tuple))
                else selected_items[0]
            )
            self.notify(f"Selected chart: {chart_name}")
            # Could launch configuration screen with pre-selected chart

    def on_config_view(self, selected_items):
        """Handle config view."""
        if selected_items:
            config_name = (
                selected_items[0][0]
                if isinstance(selected_items[0], (list, tuple))
                else selected_items[0]
            )
            # Parse cluster/app-name format
            if "/" in config_name:
                cluster_name, app_name = config_name.split("/", 1)
                
                # Load fleet.yaml from cluster-based structure
                fleet_file = core.get_apps_dir() / cluster_name / app_name / "fleet.yaml"
                configmap_file = core.get_int_dir() / cluster_name / app_name / f"{app_name}-configmap.yaml"
                
                content_data = {}
                
                # Load fleet.yaml content
                if fleet_file.exists():
                    content_data["Fleet YAML"] = fleet_file.read_text()
                else:
                    content_data["Fleet YAML"] = "Fleet configuration file not found"
                
                # Load configmap content
                if configmap_file.exists():
                    content_data["ConfigMap"] = configmap_file.read_text()
                else:
                    content_data["ConfigMap"] = "ConfigMap file not found"
                
                # Create and show the view screen
                view_screen = ViewScreen(
                    title=f"Configuration: {config_name}",
                    content_data=content_data,
                    actions=[
                        {
                            "name": "deploy",
                            "label": "Deploy",
                            "callback": lambda data: self.notify("Deploy functionality not implemented yet", severity="info")
                        }
                    ]
                )
                self.app.push_screen(view_screen)
                
            else:
                self.notify(f"Invalid config format: {config_name}", severity="error")

    def on_config_deploy(self, selected_items):
        """Handle config deployment."""
        if selected_items:
            config_name = (
                selected_items[0][0]
                if isinstance(selected_items[0], (list, tuple))
                else selected_items[0]
            )
            # Parse cluster/app-name format
            if "/" in config_name:
                cluster_name, app_name = config_name.split("/", 1)
                # Load ConfigMap from cluster-based structure in int/ directory
                configmap_file = core.get_int_dir() / cluster_name / app_name / f"{app_name}-configmap.yaml"
                if configmap_file.exists():
                    self.notify(f"Deploying config: {config_name}", severity="success")
                    # Could implement actual kubectl apply here
                else:
                    self.notify(f"ConfigMap file not found: {config_name}", severity="error")
            else:
                self.notify(f"Invalid config format: {config_name}", severity="error")

    def action_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen())

    def action_quit(self) -> None:
        """Quit application."""
        self.app.exit()

    def action_refresh(self) -> None:
        """Refresh main screen."""
        self.notify("Main screen refreshed")


class FleetConfigurationScreen(Screen):
    """Integrated Fleet configuration screen with tabs."""

    CSS = """
    FleetConfigurationScreen {
        layout: vertical;
    }
    
    #config_header {
        height: 3;
        background: $surface;
    }
    
    #config_content {
        height: 1fr;
    }
    
    #config_actions {
        height: 3;
        dock: bottom;
    }
    
    .advanced_label {
        color: $accent;
        text-style: bold;
        padding-top: 1;
        border-top: dashed $accent;
    }
    
    #namespace_list, #release_list {
        height: 8;
        min-height: 4;
    }
    
    #selected_config_label {
        color: $success;
        text-style: bold;
        background: $surface;
        padding: 1;
        border: solid $primary;
    }
    
    .hidden {
        display: none;
    }
    
    #chart_list {
        height: 8;
        min-height: 4;
    }
    
    #mode_label {
        color: $accent;
        text-style: bold;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+g", "generate", "Generate"),
        Binding("ctrl+d", "deploy", "Deploy"),
        Binding("f5", "refresh_ui", "Refresh UI"),
    ]

    def __init__(self):
        super().__init__()
        self.current_config = FleetConfig()
        self.advanced_options_shown = core.show_advanced_options()

        # Chart source mode: "repository" or "cluster"
        self.chart_source_mode = "repository"

        # Repository mode variables
        self.available_charts = []
        self.selected_chart = None

        # Cluster mode variables
        self.selected_namespace = None
        self.selected_release = None
        self.available_namespaces = []
        self.available_releases = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="config_header"):
            yield Label("🚀 Fleet Configuration Generator", classes="screen_title")

        with TabbedContent(id="config_content"):
            with TabPane("Basic Configuration", id="basic_tab"):
                yield Label("Application Name:")
                yield Input(placeholder="my-app", id="app_name")

                yield Label("Chart Source:")
                with Horizontal():
                    yield Button(
                        "📦 Helm Repository", variant="primary", id="select_repo_mode"
                    )
                    yield Button(
                        "🚀 Deployed Charts",
                        variant="default",
                        id="select_cluster_mode",
                    )

                yield Label("Selected Mode: Helm Repository", id="mode_label")

                # Repository mode (default)
                with Container(id="repo_mode_container"):
                    yield Label("Search EEA Charts:")
                    yield Input(
                        placeholder="Type chart name to search...", id="chart_search"
                    )
                    yield SelectionList(id="chart_list")
                    yield Button(
                        "Refresh Charts", variant="default", id="refresh_charts"
                    )

                # Cluster mode (hidden initially)
                with Container(id="cluster_mode_container", classes="hidden"):
                    with Horizontal():
                        with Vertical():
                            yield Label("Target Namespace:")
                            yield SelectionList(id="namespace_list")
                        yield Button(
                            "Refresh Namespaces",
                            variant="default",
                            id="refresh_namespaces",
                        )

                    with Horizontal():
                        with Vertical():
                            yield Label("Deployed Helm Releases:")
                            yield SelectionList(
                                ("Select a namespace first", None), id="release_list"
                            )
                        yield Button(
                            "Refresh Releases", variant="default", id="refresh_releases"
                        )

                yield Label("Selected Configuration:", id="selected_config_label")

            with TabPane("Chart Values", id="values_tab"):
                yield Label("Helm Values (YAML):")
                yield TextArea(
                    "# Enter your Helm values here\nreplicaCount: 1\n",
                    id="chart_values",
                )

            with TabPane("Fleet Settings", id="fleet_tab"):
                yield Label("Default Namespace:")
                yield Input(placeholder="default", id="default_namespace")

                yield Label("Target Cluster:")
                yield Input(placeholder="production", id="target_cluster")

                # Show advanced options only if setting is enabled
                if core.show_advanced_options():
                    yield Label("Advanced Fleet Options:", classes="advanced_label")
                    yield Label("Rollout Strategy:")
                    yield Input(placeholder="RollingUpdate", id="rollout_strategy")
                    yield Label("Fleet Bundle ID:")
                    yield Input(placeholder="auto-generated", id="bundle_id")
                    yield Label("Max Unavailable:")
                    yield Input(placeholder="25%", id="max_unavailable")

                yield Label("Dependencies:")
                yield TextArea(
                    "# List chart dependencies\n# - postgresql\n# - redis",
                    id="dependencies",
                )

            with TabPane("Preview", id="preview_tab"):
                yield Label("Generated Configuration:")
                yield TextArea(
                    "# Generated fleet.yaml will appear here",
                    read_only=True,
                    id="preview_content",
                )

        with Horizontal(id="config_actions"):
            yield Button(
                "Generate Configuration", variant="primary", id="generate_button"
            )
            yield Button("Deploy ConfigMap", variant="success", id="deploy_button")
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize data on screen mount."""
        # Start in repository mode by default - fast startup (no repo fetch)
        await self.refresh_charts(force_refresh=False)

        # Pre-populate namespaces for cluster mode
        self.available_namespaces = core.list_namespaces()

    def switch_to_repository_mode(self):
        """Switch to repository chart selection mode."""
        self.chart_source_mode = "repository"

        # Update UI
        self.query_one("#mode_label").update("Selected Mode: Helm Repository")
        self.query_one("#select_repo_mode").variant = "primary"
        self.query_one("#select_cluster_mode").variant = "default"

        # Show/hide containers
        self.query_one("#repo_mode_container").remove_class("hidden")
        self.query_one("#cluster_mode_container").add_class("hidden")

        # Reset only namespace/release selections, preserve chart if valid
        # self.selected_chart = None  # Let user keep their chart selection
        self.selected_namespace = None
        self.selected_release = None
        self.update_selected_config_info()

        # Load charts if not already loaded - fast mode for switching
        if not self.available_charts:
            asyncio.create_task(self.refresh_charts(force_refresh=False))

    def switch_to_cluster_mode(self):
        """Switch to deployed chart selection mode."""
        self.chart_source_mode = "cluster"

        # Update UI
        self.query_one("#mode_label").update("Selected Mode: Deployed Charts")
        self.query_one("#select_repo_mode").variant = "default"
        self.query_one("#select_cluster_mode").variant = "primary"

        # Show/hide containers
        self.query_one("#repo_mode_container").add_class("hidden")
        self.query_one("#cluster_mode_container").remove_class("hidden")

        # Reset only chart selections, preserve namespace/release if valid
        self.selected_chart = None
        # Don't reset namespace and release - let user keep their selections
        # self.selected_namespace = None
        # self.selected_release = None
        self.update_selected_config_info()

        # Load namespaces if not already loaded
        if not self.available_namespaces:
            asyncio.create_task(self.refresh_namespaces())

    async def refresh_charts(self, force_refresh: bool = False):
        """Refresh the list of available EEA charts from repository."""
        try:
            chart_list = self.query_one("#chart_list", SelectionList)
            refresh_btn = self.query_one("#refresh_charts", Button)

            # Different UI states for force refresh vs fast loading
            if force_refresh:
                # Update UI to show loading state for repository fetch
                chart_list.clear_options()
                chart_list.add_option(("🔄 Fetching charts from repository...", None))
                refresh_btn.disabled = True
                refresh_btn.label = "Refreshing..."
                # Allow repository fetch for force refresh
                self.available_charts = core.get_eea_charts(
                    force_refresh=True, allow_repo_fetch=True
                )
            else:
                # Fast mode - just show loading briefly
                chart_list.clear_options()
                chart_list.add_option(("📦 Loading charts...", None))
                # Fast mode - use cache only
                self.available_charts = core.get_eea_charts(
                    force_refresh=False, allow_repo_fetch=False
                )

            # Clear loading state and populate with charts
            chart_list.clear_options()

            if self.available_charts:
                for chart in self.available_charts:
                    category = core.categorize_chart(chart)
                    display_name = f"📦 {chart} ({category})"
                    chart_list.add_option((display_name, chart))

                if force_refresh:
                    self.notify(
                        f"Refreshed {len(self.available_charts)} EEA charts from repository",
                        severity="success",
                    )
                else:
                    self.notify(
                        f"Loaded {len(self.available_charts)} EEA charts from cache",
                        severity="success",
                    )
            else:
                chart_list.add_option(("No charts found", None))
                if force_refresh:
                    self.notify("No EEA charts found in repository", severity="warning")
                else:
                    self.notify(
                        "No cached charts found - click 'Refresh Charts' to fetch from repository",
                        severity="warning",
                    )

        except Exception as e:
            chart_list.clear_options()
            chart_list.add_option(("Error loading charts", None))
            self.notify(f"Error loading charts: {str(e)}", severity="error")
            core.log_error("refresh_charts", e)
        finally:
            # Restore refresh button state
            try:
                refresh_btn = self.query_one("#refresh_charts", Button)
                refresh_btn.disabled = False
                refresh_btn.label = "Refresh Charts"
            except:
                pass

    def filter_charts_by_search(self, search_term: str):
        """Filter charts based on search input."""
        try:
            chart_list = self.query_one("#chart_list", SelectionList)
            chart_list.clear_options()

            # Debug logging
            core.log_debug(
                "filter_charts_by_search",
                f"Search term: '{search_term}', Available charts: {len(self.available_charts) if self.available_charts else 0}",
            )

            # Ensure we have charts loaded
            if not self.available_charts:
                core.log_debug(
                    "filter_charts_by_search", "No available charts, loading from cache"
                )
                self.available_charts = core.get_eea_charts(allow_repo_fetch=False)

            if not search_term:
                # Show all charts
                for chart in self.available_charts:
                    category = core.categorize_chart(chart)
                    display_name = f"📦 {chart} ({category})"
                    chart_list.add_option((display_name, chart))
            else:
                # Filter charts
                filtered_charts = core.filter_charts(search_term, self.available_charts)
                core.log_debug(
                    "filter_charts_by_search",
                    f"Filtered results: {len(filtered_charts)} charts",
                )
                if filtered_charts:
                    for chart in filtered_charts:
                        category = core.categorize_chart(chart)
                        display_name = f"📦 {chart} ({category})"
                        chart_list.add_option((display_name, chart))
                else:
                    chart_list.add_option((f"No charts match '{search_term}'", None))

        except Exception as e:
            core.log_error("filter_charts_by_search", e, {"search_term": search_term})
            self.notify(f"Error filtering charts: {str(e)}", severity="error")

    async def refresh_namespaces(self):
        """Refresh the list of available namespaces."""
        core.log_debug("refresh_namespaces", "Starting namespace refresh")

        # Disable the refresh button during loading
        refresh_btn = self.query_one("#refresh_namespaces", Button)
        refresh_btn.disabled = True
        refresh_btn.label = "Loading..."

        try:
            namespace_list = self.query_one("#namespace_list", SelectionList)
            namespace_list.clear_options()
            namespace_list.add_option(("🔄 Loading namespaces from Rancher...", None))

            # Show loading notification
            self.notify("Loading namespaces from Rancher...", severity="info")

            # Get namespaces from Rancher
            self.available_namespaces = core.list_namespaces()
            core.log_debug(
                "refresh_namespaces",
                f"Retrieved {len(self.available_namespaces)} namespaces: {self.available_namespaces}",
            )

            namespace_list.clear_options()

            if self.available_namespaces:
                for namespace in self.available_namespaces:
                    core.log_debug(
                        "refresh_namespaces",
                        f"Adding namespace option: display='📁 {namespace}', value='{namespace}'",
                    )
                    namespace_list.add_option((f"📁 {namespace}", namespace))
                self.notify(
                    f"✅ Found {len(self.available_namespaces)} accessible namespaces",
                    severity="success",
                )
                core.log_debug(
                    "refresh_namespaces",
                    f"Successfully populated namespace list with {len(self.available_namespaces)} options",
                )
            else:
                namespace_list.add_option(("❌ No accessible namespaces found", None))
                self.notify(
                    "No accessible namespaces found. Check your Rancher connection.",
                    severity="warning",
                )
                core.log_debug("refresh_namespaces", "No namespaces found")

        except Exception as e:
            namespace_list = self.query_one("#namespace_list", SelectionList)
            namespace_list.clear_options()
            namespace_list.add_option(("❌ Error loading namespaces", None))
            self.notify(f"Error loading namespaces: {str(e)}", severity="error")
            core.log_error("refresh_namespaces", e)
        finally:
            # Re-enable the refresh button
            refresh_btn.disabled = False
            refresh_btn.label = "Refresh Namespaces"

    async def refresh_releases(self):
        """Refresh the list of Helm releases in the selected namespace."""
        # Debug logging
        core.log_debug("refresh_releases", f"Current mode: {self.chart_source_mode}")
        core.log_debug(
            "refresh_releases", f"Selected namespace: {self.selected_namespace}"
        )
        core.log_debug(
            "refresh_releases",
            f"Available namespaces: {len(self.available_namespaces)} items",
        )

        # Check if we're in cluster mode first
        if self.chart_source_mode != "cluster":
            core.log_debug("refresh_releases", "Not in cluster mode")
            self.notify("Switch to Deployed Charts mode first", severity="warning")
            return

        # Use our internal tracking which gets set when user selects from the list
        if not self.selected_namespace:
            core.log_debug(
                "refresh_releases",
                "No namespace selected - this should not happen if user clicked refresh after selecting",
            )
            self.notify("Please select a namespace first", severity="warning")
            return

        # Disable the refresh button during loading
        refresh_btn = self.query_one("#refresh_releases", Button)
        refresh_btn.disabled = True
        refresh_btn.label = "Loading..."

        try:
            # Show loading indication
            release_list = self.query_one("#release_list", SelectionList)
            release_list.clear_options()
            release_list.add_option(
                (f"🔄 Loading releases from '{self.selected_namespace}'...", None)
            )

            # Show loading notification
            self.notify(
                f"Loading Helm releases from namespace '{self.selected_namespace}'...",
                severity="info",
            )

            self.available_releases = core.list_helm_releases(self.selected_namespace)
            release_list.clear_options()

            if self.available_releases:
                for release in self.available_releases:
                    display_name = f"🚀 {release.name} ({release.chart})"
                    if hasattr(release, "chart_version") and release.chart_version:
                        display_name += f" v{release.chart_version}"
                    display_name += f" - {release.status}"
                    # Store only the release name as value to avoid unmarshal/type issues in TUI
                    release_list.add_option((display_name, release.name))
                self.notify(
                    f"✅ Found {len(self.available_releases)} Helm releases in '{self.selected_namespace}'",
                    severity="success",
                )
            else:
                release_list.add_option(
                    ("❌ No Helm releases found in this namespace", None)
                )
                self.notify(
                    f"No Helm releases found in namespace '{self.selected_namespace}'. Try selecting a different namespace.",
                    severity="warning",
                )

        except Exception as e:
            release_list = self.query_one("#release_list", SelectionList)
            release_list.clear_options()
            release_list.add_option(("❌ Error loading releases", None))
            self.notify(f"Error loading releases: {str(e)}", severity="error")
        finally:
            # Re-enable the refresh button
            refresh_btn.disabled = False
            refresh_btn.label = "Refresh Releases"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for chart search."""
        if event.input.id == "chart_search":
            self.filter_charts_by_search(event.value)

    def on_selection_list_option_selected(
        self, event: SelectionList.OptionSelected
    ) -> None:
        """Handle selection changes in all selection lists."""
        # Debug logging for all selections
        core.log_debug(
            "on_selection_list_option_selected",
            f"Selection in list {event.selection_list.id}: option={event.option}, value={event.option.value if event.option else None}",
        )

        if event.selection_list.id == "chart_list":
            # Repository mode chart selection
            self.selected_chart = (
                event.option.value if event.option and event.option.value else None
            )
            core.log_debug(
                "on_selection_list_option_selected",
                f"Chart selected: {self.selected_chart}",
            )
            if self.selected_chart:
                self.notify(f"Selected chart: {self.selected_chart}")
                # Load default values for the selected chart
                self.load_chart_default_values()
                # Update configuration info
                self.update_selected_config_info()

        elif event.selection_list.id == "namespace_list":
            # Cluster mode namespace selection - Enhanced debugging
            core.log_debug(
                "namespace_selection",
                f"Raw event - option: {event.option}, has_value: {hasattr(event.option, 'value') if event.option else False}",
            )

            if event.option and hasattr(event.option, "value") and event.option.value:
                self.selected_namespace = event.option.value
                core.log_debug(
                    "namespace_selection",
                    f"SUCCESS - Namespace selected: {self.selected_namespace}",
                )
                self.notify(f"Selected namespace: {self.selected_namespace}")

                # Clear release selection when namespace changes
                self.selected_release = None
                release_list = self.query_one("#release_list", SelectionList)
                release_list.clear_options()
                release_list.add_option(("Loading releases...", None))
                # Auto-refresh releases
                asyncio.create_task(self.refresh_releases())
                # Update configuration info
                self.update_selected_config_info()
            else:
                core.log_debug(
                    "namespace_selection",
                    f"FAILED - No valid namespace value. Option: {event.option}",
                )
                self.selected_namespace = None

        elif event.selection_list.id == "release_list":
            # Cluster mode release selection
            self.selected_release = event.option.value if event.option.value else None
            core.log_debug(
                "on_selection_list_option_selected",
                f"Release selected: {self.selected_release}",
            )
            if self.selected_release:
                self.notify(f"Selected release: {self.selected_release.name}")
                # Auto-load values from the selected release
                asyncio.create_task(self.load_release_values())
                # Update the configuration info
                self.update_selected_config_info()

    def on_selection_list_selected_changed(
        self, message: SelectionList.SelectedChanged
    ) -> None:
        """Handle SelectionList selection changes (Textual 5+)."""
        selection_list = message.selection_list
        list_id = getattr(selection_list, "id", None)
        selected_repr = None
        try:
            selected_repr = getattr(selection_list, "selected", None)
        except Exception:
            selected_repr = None
        core.log_debug(
            "on_selection_list_selected_changed",
            f"List: {list_id}, selected: {selected_repr}",
        )

        # Helper to extract the value object from the current selection, across Textual API variations
        def _extract_selected_value() -> Optional[str | object]:
            selected_tokens = selected_repr or []
            if not selected_tokens:
                return None
            first_token = selected_tokens[0]
            # Attempt 1: token-compatible get_selection → returns (label, value)
            try:
                pair = selection_list.get_selection(first_token)
                if pair and len(pair) == 2 and pair[1] is not None:
                    return pair[1]
            except Exception:
                pass
            # Attempt 2: if SelectionList.selected yields the value directly (e.g., a str namespace)
            if isinstance(first_token, str):
                return first_token
            # Attempt 3: if it's an index, try to resolve via get_option_at_index
            try:
                option = selection_list.get_option_at_index(first_token)  # type: ignore[arg-type]
                # Option might not expose value directly; try mapping via get_selection if possible
                try:
                    pair2 = selection_list.get_selection(first_token)
                    if pair2 and len(pair2) == 2 and pair2[1] is not None:
                        return pair2[1]
                except Exception:
                    pass
                # Last resort: if option has a "value" attribute
                val = getattr(option, "value", None)
                if val is not None:
                    return val
            except Exception:
                pass
            return None

        if list_id == "namespace_list":
            value = _extract_selected_value()
            if value:
                # If the value is the label, map it to a known namespace value when possible
                if isinstance(value, str):
                    self.selected_namespace = value
                else:
                    # Unexpected type, fallback to string representation
                    self.selected_namespace = str(value)
                core.log_debug(
                    "namespace_selected_changed",
                    f"Namespace set to: {self.selected_namespace}",
                )
                self.notify(f"Selected namespace: {self.selected_namespace}")

                # Reset release list and trigger refresh
                self.selected_release = None
                release_list = self.query_one("#release_list", SelectionList)
                release_list.clear_options()
                release_list.add_option(("Loading releases...", None))
                asyncio.create_task(self.refresh_releases())
                self.update_selected_config_info()
            else:
                core.log_debug("namespace_selected_changed", "No valid selection")
                self.selected_namespace = None

        elif list_id == "release_list":
            value = _extract_selected_value()
            if value:
                # Value is the release name (string). Map to HelmRelease object from cache.
                normalized_release = None
                if isinstance(value, str):
                    candidate_name = value.split(" ")[0]
                    for rel in self.available_releases:
                        if getattr(rel, "name", None) == candidate_name:
                            normalized_release = rel
                            break
                elif hasattr(value, "name") and hasattr(value, "chart"):
                    normalized_release = value

                if normalized_release is None:
                    core.log_debug(
                        "release_selected_changed",
                        f"Could not map selection to release object: {value}",
                    )
                    return

                self.selected_release = normalized_release
                core.log_debug(
                    "release_selected_changed",
                    f"Release set to: {self.selected_release}",
                )
                # Debug chart object
                core.log_chart_debug(self.selected_release, "release_selected_chart")
                # Debug fleet context
                core.log_fleet_context_debug("release_selected_context")
                try:
                    self.notify(f"Selected release: {self.selected_release.name}")
                except Exception:
                    pass
                asyncio.create_task(self.load_release_values())
                # Prefill fleet settings with release and cluster data
                self.prefill_fleet_settings()
                self.update_selected_config_info()
            else:
                self.selected_release = None
                core.log_debug("release_selected_changed", "No valid selection")

        elif list_id == "chart_list":
            value = _extract_selected_value()
            if value:
                self.selected_chart = value if isinstance(value, str) else str(value)
                core.log_debug(
                    "chart_selected_changed", f"Chart set to: {self.selected_chart}"
                )
                self.notify(f"Selected chart: {self.selected_chart}")
                self.load_chart_default_values()
                self.update_selected_config_info()
            else:
                self.selected_chart = None

    def load_chart_default_values(self):
        """Load default values for the selected repository chart."""
        if not self.selected_chart:
            return

        try:
            default_values = core.get_default_helm_values(self.selected_chart)
            values_yaml = yaml.dump(default_values, default_flow_style=False)
            self.query_one("#chart_values").text = values_yaml
            self.notify(
                f"Loaded default values for chart '{self.selected_chart}'",
                severity="success",
            )
        except Exception as e:
            self.notify(f"Error loading default values: {str(e)}", severity="error")

    async def load_release_values(self):
        """Load values from the selected Helm release."""
        if not self.selected_release or not self.selected_namespace:
            return

        try:
            values = core.get_helm_release_values(
                self.selected_release.name, self.selected_namespace
            )
            if values:
                values_yaml = yaml.dump(values, default_flow_style=False)
                self.query_one("#chart_values").text = values_yaml
                self.notify(
                    f"Loaded values from release '{self.selected_release.name}'",
                    severity="success",
                )
            else:
                self.notify(
                    f"No custom values found for release '{self.selected_release.name}'",
                    severity="info",
                )
        except Exception as e:
            self.notify(f"Error loading release values: {str(e)}", severity="error")

    def prefill_fleet_settings(self):
        """Prefill Fleet Settings tab with data from selected release and current Rancher cluster."""
        if not self.selected_release or not self.selected_namespace:
            return

        try:
            # Get current cluster information
            context, cluster_id, cluster_name = core.get_current_rancher_context()

            # Prefill default namespace with the release's namespace
            default_namespace_input = self.query_one("#default_namespace", Input)
            if not default_namespace_input.value.strip():
                default_namespace_input.value = self.selected_namespace

            # Prefill target cluster with current cluster name
            target_cluster_input = self.query_one("#target_cluster", Input)
            if not target_cluster_input.value.strip() and cluster_name:
                target_cluster_input.value = cluster_name

            # Extract dependencies from chart metadata or common patterns
            dependencies_area = self.query_one("#dependencies", TextArea)
            if (
                not dependencies_area.text.strip()
                or dependencies_area.text.strip().startswith(
                    "# List chart dependencies"
                )
            ):
                # Try to get chart dependencies
                dependencies = self._extract_chart_dependencies()
                if dependencies:
                    deps_text = "# Dependencies extracted from chart:\n" + "\n".join(
                        [f"# - {dep}" for dep in dependencies]
                    )
                    dependencies_area.text = deps_text

            self.notify(
                "Fleet settings prefilled with release data", severity="success"
            )

        except Exception as e:
            core.log_debug("prefill_fleet_settings", f"Error prefilling: {str(e)}")

    def _extract_chart_dependencies(self) -> List[str]:
        """Extract chart dependencies from the selected release."""
        dependencies = []
        if not self.selected_release:
            return dependencies

        try:
            # Try to get helm chart metadata
            chart_name = (
                self.selected_release.chart.split("/")[-1]
                if "/" in self.selected_release.chart
                else self.selected_release.chart
            )

            # Common dependencies based on chart name patterns
            if "backend" in chart_name.lower() or "api" in chart_name.lower():
                dependencies.extend(["postgresql", "redis"])
            elif "frontend" in chart_name.lower() or "ui" in chart_name.lower():
                dependencies.extend(["nginx-ingress"])
            elif "database" in chart_name.lower() or "db" in chart_name.lower():
                dependencies.extend(["persistent-volume"])

            return dependencies

        except Exception as e:
            core.log_debug(
                "_extract_chart_dependencies",
                f"Error extracting dependencies: {str(e)}",
            )
            return []

    def update_selected_config_info(self):
        """Update the selected configuration info label."""
        core.log_debug(
            "update_selected_config_info",
            f"Mode: {self.chart_source_mode}, Chart: {self.selected_chart}, Namespace: {self.selected_namespace}, Release: {self.selected_release}",
        )

        if self.chart_source_mode == "repository":
            if self.selected_chart:
                category = core.categorize_chart(self.selected_chart)
                info = f"✅ Repository Chart: {self.selected_chart} ({category}) | Source: EEA Helm Repository"
            else:
                info = "⏳ Repository Mode: Please select a chart from the list above"
        elif self.chart_source_mode == "cluster":
            if self.selected_release and self.selected_namespace:
                info = f"✅ Deployed Release: {self.selected_release.name} | Chart: {self.selected_release.chart} | Namespace: {self.selected_namespace}"
            elif self.selected_namespace:
                info = f"⏳ Cluster Mode: Namespace '{self.selected_namespace}' selected - Please select a Helm release"
            else:
                info = "⏳ Cluster Mode: Please select a namespace first, then a Helm release"
        else:
            info = "❓ Unknown configuration state"

        self.query_one("#selected_config_label").update(info)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        # Debug logging for all button presses
        core.log_debug("on_button_pressed", f"Button pressed: {event.button.id}")
        core.log_debug(
            "on_button_pressed",
            f"Current mode: {self.chart_source_mode}, namespace: {self.selected_namespace}, chart: {self.selected_chart}, release: {self.selected_release}",
        )

        if event.button.id == "back_button":
            self.app.pop_screen()
        elif event.button.id == "select_repo_mode":
            self.switch_to_repository_mode()
        elif event.button.id == "select_cluster_mode":
            self.switch_to_cluster_mode()
        elif event.button.id == "refresh_charts":
            asyncio.create_task(self.refresh_charts(force_refresh=True))
        elif event.button.id == "refresh_namespaces":
            asyncio.create_task(self.refresh_namespaces())
        elif event.button.id == "refresh_releases":
            asyncio.create_task(self.refresh_releases())
        elif event.button.id == "generate_button":
            self.generate_configuration()
        elif event.button.id == "deploy_button":
            self.deploy_configuration()

    def generate_configuration(self):
        """Generate Fleet configuration from selected chart (repository or deployed)."""
        # Debug logging
        core.log_debug(
            "generate_configuration",
            f"Starting generation in mode: {self.chart_source_mode}",
        )
        core.log_debug(
            "generate_configuration", f"Selected chart: {self.selected_chart}"
        )
        core.log_debug(
            "generate_configuration", f"Selected namespace: {self.selected_namespace}"
        )
        core.log_debug(
            "generate_configuration", f"Selected release: {self.selected_release}"
        )

        # Debug chart object and fleet context as requested
        if self.selected_release:
            core.log_chart_debug(self.selected_release, "generate_config_chart")
        if self.selected_chart:
            core.log_debug(
                "generate_configuration",
                f"Chart object type: {type(self.selected_chart)}",
            )
            if hasattr(self.selected_chart, "__dict__"):
                core.log_debug(
                    "generate_configuration",
                    f"Chart object dict: {self.selected_chart.__dict__}",
                )
        core.log_fleet_context_debug("generate_config_context")

        app_name = self.query_one("#app_name").value
        core.log_debug("generate_configuration", f"App name: {app_name}")

        if not app_name:
            self.notify("Please enter an application name", severity="error")
            return

        if self.chart_source_mode == "repository":
            core.log_debug("generate_configuration", "Processing repository mode")

            # Repository mode validation
            if not self.selected_chart:
                core.log_debug(
                    "generate_configuration", "No chart selected in repository mode"
                )
                self.notify(
                    "Please select a chart from the repository first", severity="error"
                )
                return

            # Build configuration from repository chart
            self.current_config.app_name = app_name
            self.current_config.chart_name = self.selected_chart
            self.current_config.chart_version = "latest"  # Default for repo charts
            self.current_config.helm_repo = core.EEA_HELM_REPO

            # Get target namespace and cluster from Fleet Settings tab
            self.current_config.target_cluster = self.query_one("#target_cluster").value

            # For repository mode, get namespace from Fleet Settings tab
            default_namespace = self.query_one("#default_namespace").value
            if default_namespace:
                self.current_config.namespace = default_namespace
            else:
                # Fallback to app name if no namespace specified
                self.current_config.namespace = app_name

            core.log_debug(
                "generate_configuration",
                f"Repository config: chart={self.selected_chart}, namespace={self.current_config.namespace}, target_cluster={self.current_config.target_cluster}",
            )

        elif self.chart_source_mode == "cluster":
            core.log_debug("generate_configuration", "Processing cluster mode")

            # Cluster mode validation
            if not self.selected_namespace:
                core.log_debug(
                    "generate_configuration", "No namespace selected in cluster mode"
                )
                self.notify("Please select a namespace first", severity="error")
                return

            if not self.selected_release:
                core.log_debug(
                    "generate_configuration", "No release selected in cluster mode"
                )
                self.notify("Please select a Helm release first", severity="error")
                return

            # Build configuration from deployed release
            self.current_config.app_name = app_name
            self.current_config.namespace = self.selected_namespace
            self.current_config.chart_name = self.selected_release.chart
            self.current_config.chart_version = (
                self.selected_release.chart_version or "latest"
            )
            self.current_config.target_cluster = self.query_one("#target_cluster").value

            # Mark as existing release and set release name for secret metadata extraction
            self.current_config.is_existing_release = True
            self.current_config.release_name = self.selected_release.name

            # Store any additional metadata from the release
            self.current_config.chart_metadata = {
                "name": self.selected_release.chart,
                "version": self.selected_release.chart_version,
                "appVersion": self.selected_release.app_version,
            }

            core.log_debug(
                "generate_configuration",
                f"Cluster config: chart={self.selected_release.chart}, namespace={self.selected_namespace}, release={self.selected_release.name}, metadata={self.current_config.chart_metadata}",
            )

        # Parse values from the text area
        try:
            values_text = self.query_one("#chart_values").text
            self.current_config.values = yaml.safe_load(values_text) or {}
            core.log_debug(
                "generate_configuration",
                f"Parsed values: {len(self.current_config.values)} keys",
            )
        except Exception as e:
            core.log_debug("generate_configuration", f"Values parsing error: {str(e)}")
            self.notify(f"Error parsing values: {str(e)}", severity="error")
            return

        # Get current cluster information
        context, cluster_id, cluster_name = core.get_current_rancher_context()
        
        # Use cluster_name if available, fallback to cluster_id, or 'default' if neither exists
        cluster_folder = cluster_name or cluster_id or "default"
        cluster_folder = cluster_folder.replace("/", "-").replace("_", "-")  # Ensure safe folder naming
        
        # App directory name remains <namespace>-<chart> for RFC 1123 compliance
        app_dir_name = (
            f"{self.current_config.namespace}-{self.current_config.chart_name}"
        )
        app_dir_name = app_dir_name.replace("/", "-").replace("_", "-")  # Ensure RFC 1123 compliance
        # Normalize the internal app_name to match the bundle/configmap naming convention
        self.current_config.app_name = app_dir_name

        # Generate configuration (after app_name normalization so valuesFrom references align)
        fleet_yaml = core.generate_fleet_yaml(self.current_config)
        values_yaml = core.generate_values_yaml(self.current_config)
        configmap_yaml = core.generate_configmap_yaml(self.current_config)

        # apps/<cluster>/<namespace>-<chart>/fleet_config.yaml (metadata)
        app_dir = core.get_apps_dir() / cluster_folder / app_dir_name
        app_dir.mkdir(parents=True, exist_ok=True)
        # (app_dir / "fleet_config.yaml").write_text(
        #     yaml.dump({
        #         "app_name": self.current_config.app_name,
        #         "namespace": self.current_config.namespace,
        #         "chart_name": self.current_config.chart_name,
        #         "chart_version": self.current_config.chart_version,
        #         "helm_repo": self.current_config.helm_repo,
        #         "target_cluster": self.current_config.target_cluster,
        #         "dependencies": self.current_config.dependencies,
        #     }, default_flow_style=False)
        # )

        # apps/<cluster>/<namespace>-<chart>/fleet.yaml (Fleet configuration)
        (app_dir / "fleet.yaml").write_text(fleet_yaml)

        # int/<cluster>/<namespace>-<chart>/<namespace>-<chart>-configmap.yaml (ConfigMap with values)
        int_dir = core.get_int_dir() / cluster_folder / app_dir_name
        int_dir.mkdir(parents=True, exist_ok=True)
        (int_dir / f"{app_dir_name}-configmap.yaml").write_text(configmap_yaml)

        # Show preview
        preview_content = f"# fleet.yaml\n{fleet_yaml}\n\n# values.yaml\n{values_yaml}"
        self.query_one("#preview_content").text = preview_content

        # Update notification based on mode
        if self.chart_source_mode == "repository":
            self.notify(
                f"Configuration generated for chart '{self.selected_chart}' from repository",
                severity="success",
            )
        else:
            self.notify(
                f"Configuration generated for release '{self.selected_release.name}' ({self.selected_release.chart})",
                severity="success",
            )

    def deploy_configuration(self):
        """Deploy configuration as ConfigMap."""
        # Debug logging
        core.log_debug(
            "deploy_configuration",
            f"Starting deployment in mode: {self.chart_source_mode}",
        )
        core.log_debug(
            "deploy_configuration", f"Config app_name: {self.current_config.app_name}"
        )
        core.log_debug(
            "deploy_configuration", f"Config namespace: {self.current_config.namespace}"
        )
        core.log_debug(
            "deploy_configuration", f"Selected namespace: {self.selected_namespace}"
        )

        if not self.current_config.app_name:
            core.log_debug("deploy_configuration", "No app name in current config")
            self.notify("Please generate configuration first", severity="error")
            return

        # Validate namespace is set in the configuration (not selected_namespace)
        if not self.current_config.namespace:
            core.log_debug("deploy_configuration", "No namespace in current config")
            if self.chart_source_mode == "cluster":
                self.notify("Please select a namespace first", severity="error")
            else:
                self.notify(
                    "Please set a namespace in Fleet Settings or select one",
                    severity="error",
                )
            return

        # Deploy using core function
        core.log_debug(
            "deploy_configuration",
            f"Deploying to namespace: {self.current_config.namespace}",
        )
        success, message = core.deploy_configmap(self.current_config)

        core.log_debug(
            "deploy_configuration",
            f"Deploy result: success={success}, message={message[:100]}",
        )

        if success:
            self.notify(message, severity="success")
        else:
            self.notify(message, severity="error")

    def action_refresh_ui(self) -> None:
        """Refresh the UI to show/hide advanced options based on current settings."""
        current_advanced_setting = core.show_advanced_options()

        if current_advanced_setting != self.advanced_options_shown:
            self.advanced_options_shown = current_advanced_setting
            self.notify("UI refreshed! Advanced options updated.", severity="info")
            # Force screen refresh by popping and pushing the same screen
            self.app.pop_screen()
            self.app.push_screen(create_fleet_configuration_screen())
        else:
            self.notify("UI is up to date with current settings.", severity="info")

    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def action_generate(self) -> None:
        """Generate configuration."""
        self.generate_configuration()

    def action_deploy(self) -> None:
        """Deploy configuration."""
        self.deploy_configuration()


class SettingsScreen(Screen):
    """Application settings screen."""

    CSS = """
    SettingsScreen {
        layout: vertical;
    }
    
    #settings_content {
        padding: 2;
        height: 1fr;
    }
    
    #settings_actions {
        height: 3;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="settings_content"):
            yield Label("⚙️ Application Settings", classes="screen_title")

            yield Label("Directory Configuration:")
            yield Label("Apps Directory:")
            yield Input(value=str(core.get_apps_dir()), id="apps_dir")
            yield Button("Browse Apps Directory", id="browse_apps_dir")

            yield Label("Integration Directory:")
            yield Input(value=str(core.get_int_dir()), id="int_dir")
            yield Button("Browse Int Directory", id="browse_int_dir")

            yield Label("Rancher Settings:")
            yield Label("Current Context:")
            context, cluster_id, cluster_name = core.get_current_rancher_context()
            yield Label(f"{context or 'Not set'}", id="current_context_label")
            yield Button("Switch Rancher Context", id="switch_context")

            yield Label("UI Settings:")
            yield Checkbox(
                "Show advanced options",
                id="show_advanced",
                value=core.get_setting("show_advanced", False),
            )
            yield Checkbox(
                "Auto-refresh data",
                id="auto_refresh",
                value=core.get_setting("auto_refresh", True),
            )

        with Horizontal(id="settings_actions"):
            yield Button("Save Settings", variant="primary", id="save_button")
            yield Button("Reset to Defaults", variant="error", id="reset_button")
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()
        elif event.button.id == "save_button":
            self.save_settings()
        elif event.button.id == "reset_button":
            self.reset_settings()
        elif event.button.id == "browse_apps_dir":
            self.browse_directory("apps_dir")
        elif event.button.id == "browse_int_dir":
            self.browse_directory("int_dir")
        elif event.button.id == "switch_context":
            self.switch_rancher_context()

    def browse_directory(self, dir_type: str):
        """Browse for directory."""
        fields = [
            {
                "name": "directory_path",
                "label": "Select Directory",
                "type": "directory",
                "required": True,
            }
        ]
        self.app.push_screen(
            BaseInputScreen(f"Select {dir_type.title()} Directory", fields),
            callback=lambda result: self.on_directory_selected(result, dir_type),
        )

    def on_directory_selected(self, result, dir_type: str):
        """Handle directory selection."""
        if result:
            directory = result.get("directory_path", "")
            if dir_type == "apps_dir":
                self.query_one("#apps_dir").value = directory
            elif dir_type == "int_dir":
                self.query_one("#int_dir").value = directory

    def switch_rancher_context(self):
        """Show Rancher context switching screen."""
        contexts = core.list_rancher_contexts()
        if not contexts:
            self.notify("No Rancher contexts available", severity="error")
            return

        context_screen = BaseListScreen(
            title="Select Rancher Context",
            data_service=lambda: [
                (ctx.project_id, ctx.number, ctx.cluster_name, ctx.project_name)
                for ctx in contexts
            ],
            columns=["Namespace ID", "#", "Cluster", "Project"],
            actions=[
                {
                    "name": "switch",
                    "label": "Switch Context",
                    "callback": self.on_context_switch,
                }
            ],
        )
        self.app.push_screen(context_screen)

    def on_context_switch(self, selected_items):
        """Handle context switch."""
        if selected_items:
            namespace_id = selected_items[0][0]  # First column is now the namespace ID
            success = core.switch_rancher_context(namespace_id)
            if success:
                self.notify("Context switched successfully!", severity="success")
                # Update display
                context, cluster_id, cluster_name = core.get_current_rancher_context()
                self.query_one("#current_context_label").update(context or "Not set")
            else:
                self.notify("Failed to switch context", severity="error")

    def save_settings(self):
        """Save application settings."""
        old_advanced_setting = core.get_setting("show_advanced", False)

        settings = {
            "apps_dir": self.query_one("#apps_dir").value,
            "int_dir": self.query_one("#int_dir").value,
            "show_advanced": self.query_one("#show_advanced").value,
            "auto_refresh": self.query_one("#auto_refresh").value,
        }

        if core.save_settings(settings):
            # Update directories
            core.initialize_directories()

            # If advanced setting changed, notify user they need to navigate to other screens
            new_advanced_setting = settings["show_advanced"]
            if old_advanced_setting != new_advanced_setting:
                if new_advanced_setting:
                    self.notify(
                        "Settings saved! Advanced options enabled. Visit Fleet Configuration or Rancher Setup and press F5 to refresh UI.",
                        severity="success",
                        timeout=8,
                    )
                else:
                    self.notify(
                        "Settings saved! Advanced options disabled. Press F5 on other screens to refresh the UI.",
                        severity="success",
                        timeout=8,
                    )
            else:
                self.notify("Settings saved successfully!", severity="success")
        else:
            self.notify("Failed to save settings", severity="error")

    def reset_settings(self):
        """Reset settings to defaults."""
        self.query_one("#apps_dir").value = "apps"
        self.query_one("#int_dir").value = "int"
        self.query_one("#show_advanced").value = False
        self.query_one("#auto_refresh").value = True
        self.notify("Settings reset to defaults")

    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def action_save(self) -> None:
        """Save settings."""
        self.save_settings()


class RancherSetupScreen(Screen):
    """Rancher setup and connection testing screen."""

    CSS = """
    RancherSetupScreen {
        layout: vertical;
    }
    
    #setup_content {
        padding: 2;
        height: 1fr;
    }
    
    #setup_actions {
        height: 3;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("f5", "refresh_ui", "Refresh UI"),
    ]

    def __init__(self):
        super().__init__()
        self.advanced_options_shown = core.show_advanced_options()

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="setup_content"):
            yield Label("🏗️ Rancher Connection Setup", classes="screen_title")

            yield Label("Current Status:")
            yield Label("Checking connection...", id="connection_status")

            yield Label("Available Commands:")
            yield Button("Test Rancher Connection", id="test_connection")
            yield Button("List Available Contexts", id="list_contexts")
            yield Button("Check Cluster Access", id="check_cluster")

            # Show advanced diagnostic options if setting is enabled
            if core.show_advanced_options():
                yield Label("Advanced Diagnostics:", classes="advanced_label")
                yield Button("Debug Rancher Config", id="debug_config")
                yield Button("Test Kubeconfig Generation", id="test_kubeconfig")
                yield Button("Validate Namespace Access", id="validate_namespaces")

            yield Label("Connection Log:")
            yield Log(id="setup_log")

        with Horizontal(id="setup_actions"):
            yield Button("Refresh Status", variant="primary", id="refresh_button")
            yield Button("Back", variant="default", id="back_button")

        yield Footer()

    async def on_mount(self) -> None:
        """Check connection status on mount."""
        await self.check_connection_status()

    async def check_connection_status(self):
        """Check current Rancher connection status."""
        log = self.query_one("#setup_log", Log)
        status_label = self.query_one("#connection_status")

        log.write_line("Checking Rancher CLI...")

        try:
            success, output = core.run_rancher_command(["--version"])
            if success:
                log.write_line(f"Rancher CLI found: {output.strip()}")

                # Check if logged in
                success, output = core.run_rancher_command(["context", "current"])
                if success:
                    status_label.update(f"✅ Connected: {output.strip()}")
                    log.write_line(f"Current context: {output.strip()}")
                else:
                    status_label.update("❌ Not logged in to Rancher")
                    log.write_line("Not logged in to Rancher")
            else:
                status_label.update("❌ Rancher CLI not found")
                log.write_line("Rancher CLI not found or not in PATH")

        except Exception as e:
            status_label.update(f"❌ Error: {str(e)}")
            log.write_line(f"Error checking connection: {str(e)}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()
        elif event.button.id == "refresh_button":
            asyncio.create_task(self.check_connection_status())
        elif event.button.id == "test_connection":
            self.test_connection()
        elif event.button.id == "list_contexts":
            self.list_contexts()
        elif event.button.id == "check_cluster":
            self.check_cluster_access()
        elif event.button.id == "debug_config":
            self.debug_rancher_config()
        elif event.button.id == "test_kubeconfig":
            self.test_kubeconfig_generation()
        elif event.button.id == "validate_namespaces":
            self.validate_namespace_access()

    def test_connection(self):
        """Test Rancher connection."""
        log = self.query_one("#setup_log", Log)
        log.write_line("Testing Rancher connection...")

        success, output = core.run_rancher_command(["kubectl", "version", "--client"])
        if success:
            log.write_line(f"✅ Kubectl available via Rancher: {output.strip()}")
        else:
            log.write_line(f"❌ Kubectl test failed: {output}")

    def list_contexts(self):
        """List available contexts."""
        log = self.query_one("#setup_log", Log)
        log.write_line("Listing available contexts...")

        contexts = core.list_rancher_contexts()
        if contexts:
            log.write_line(f"Found {len(contexts)} contexts:")
            for ctx in contexts:
                log.write_line(
                    f"  {ctx.number}: {ctx.cluster_name} / {ctx.project_name}"
                )
        else:
            log.write_line("No contexts found")

    def check_cluster_access(self):
        """Check cluster access."""
        log = self.query_one("#setup_log", Log)
        log.write_line("Checking cluster access...")

        success, message = core.check_cluster_connectivity()
        if success:
            log.write_line(f"✅ {message}")

            # Also list namespaces as additional test
            namespaces = core.list_namespaces()
            log.write_line(f"Accessible namespaces: {len(namespaces)}")
        else:
            log.write_line(f"❌ {message}")

    def debug_rancher_config(self):
        """Debug Rancher configuration and settings."""
        log = self.query_one("#setup_log", Log)
        log.write_line("=== Debug Rancher Configuration ===")

        # Show current context
        context, cluster_id, cluster_name = core.get_current_rancher_context()
        log.write_line(f"Current context: {context}")
        log.write_line(f"Cluster ID: {cluster_id}")
        log.write_line(f"Cluster name: {cluster_name}")

        # Show settings
        settings = core._settings
        log.write_line(f"Current settings: {json.dumps(settings, indent=2)}")

        # Test raw rancher command
        success, output = core.run_rancher_command(["context", "current"])
        log.write_line(
            f"Raw rancher context: {output if success else f'ERROR: {output}'}"
        )

    def test_kubeconfig_generation(self):
        """Test kubeconfig generation process."""
        log = self.query_one("#setup_log", Log)
        log.write_line("=== Testing Kubeconfig Generation ===")

        kubeconfig_path = core.generate_temp_kubeconfig()
        if kubeconfig_path:
            log.write_line(f"✅ Kubeconfig generated: {kubeconfig_path}")

            # Test if file exists and is valid
            try:
                with open(kubeconfig_path, "r") as f:
                    content = f.read()
                    log.write_line(f"Kubeconfig size: {len(content)} bytes")
                    if "apiVersion" in content and "clusters" in content:
                        log.write_line("✅ Kubeconfig appears valid")
                    else:
                        log.write_line("⚠️ Kubeconfig may be invalid")

                # Show current kubeconfig path
                current_config = core.get_current_kubeconfig()
                log.write_line(f"Current kubeconfig path: {current_config}")

            except Exception as e:
                log.write_line(f"❌ Error reading kubeconfig: {str(e)}")
        else:
            log.write_line("❌ Failed to generate kubeconfig")

    def validate_namespace_access(self):
        """Validate namespace access in detail."""
        log = self.query_one("#setup_log", Log)
        log.write_line("=== Validating Namespace Access ===")

        namespaces = core.list_namespaces()
        log.write_line(f"Found {len(namespaces)} namespaces:")

        for namespace in namespaces:
            log.write_line(f"  - {namespace}")

            # Test namespace existence
            exists = core.namespace_exists(namespace)
            log.write_line(f"    Exists: {exists}")

            # Test validation
            can_access, message = core.validate_namespace_access(namespace)
            log.write_line(f"    Accessible: {can_access} - {message}")

    def action_refresh_ui(self) -> None:
        """Refresh the UI to show/hide advanced options based on current settings."""
        current_advanced_setting = core.show_advanced_options()

        if current_advanced_setting != self.advanced_options_shown:
            self.advanced_options_shown = current_advanced_setting
            self.notify("UI refreshed! Advanced diagnostics updated.", severity="info")
            # Force screen refresh by popping and pushing the same screen
            self.app.pop_screen()
            self.app.push_screen(create_rancher_setup_screen())
        else:
            self.notify("UI is up to date with current settings.", severity="info")

    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()


class HelpScreen(ViewScreen):
    """Help screen with documentation."""

    def __init__(self):
        content = {
            "Help": HELP_TEXT_CONTENT,
            "Keyboard Shortcuts": self.get_shortcuts_content(),
        }
        super().__init__("❓ Help & Documentation", content)

    def get_shortcuts_content(self) -> str:
        """Get keyboard shortcuts content."""
        return """
# Keyboard Shortcuts

## Global Shortcuts
- **Escape**: Go back to previous screen
- **Ctrl+R**: Refresh current view
- **Ctrl+Q**: Quit application
- **H**: Show help (from main screen)

## Fleet Configuration Screen
- **Ctrl+G**: Generate configuration
- **Ctrl+D**: Deploy configuration
- **F5**: Refresh UI (for advanced options)

## Rancher Setup Screen  
- **F5**: Refresh UI (for advanced diagnostics)

## List Screens
- **Ctrl+S**: Focus search input
- **Ctrl+R**: Refresh data
- **Enter**: Select item

## Process Screens
- **Ctrl+C**: Stop running process
- **Ctrl+L**: Clear log

## Settings Screen
- **Ctrl+S**: Save settings
- **Ctrl+R**: Reset to defaults
        """


# Create screen factory functions for backwards compatibility
def create_main_screen() -> MainScreen:
    """Create main screen instance."""
    return MainScreen()


def create_fleet_configuration_screen() -> FleetConfigurationScreen:
    """Create fleet configuration screen instance."""
    return FleetConfigurationScreen()


def create_settings_screen() -> SettingsScreen:
    """Create settings screen instance."""
    return SettingsScreen()


def create_help_screen() -> HelpScreen:
    """Create help screen instance."""
    return HelpScreen()


def create_rancher_setup_screen() -> RancherSetupScreen:
    """Create Rancher setup screen instance."""
    return RancherSetupScreen()

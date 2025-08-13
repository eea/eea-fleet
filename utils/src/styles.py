"""
CSS Styles for EEA Fleet Configuration Generator TUI
"""

MAIN_CSS = """
Screen {
    align: center middle;
}
#banner {
    text-align: center;
    color: $primary;
    margin: 1;
}

#subtitle {
    text-align: center;
    color: $secondary;
    margin-bottom: 1;
}

#chart-count {
    text-align: center;
    color: $accent;
    margin-bottom: 2;
}

#main-content {
    align: center middle;
    width: 100%;
    height: 100%;
}

#main-menu {
    align: center middle;
    width: 50%;
    text-align: center;
}

#main-menu Button {
    width: 100%;
    text-align: center;
}

#prerequisites-dialog {
    align: center middle;
    width: 80%;
    height: 60%;
    border: thick $primary 80%;
    background: $surface;
}

#prerequisites-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#prerequisites-buttons {
    align: center bottom;
    height: auto;
    margin-top: 1;
}

#prerequisites-buttons Button {
    margin: 0 1;
}

.screen {
    align: center middle;
}

#chart-selector-title, #config-title, #generation-title, #deploy-title, #charts-title, #configs-title, #help-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#chart-search, #charts-search {
    margin-bottom: 1;
}

#chart-list-container {
    height: 60%;
    border: round $primary;
    margin-bottom: 1;
}

#config-form {
    width: 80%;
    align: center middle;
    margin-bottom: 2;
}

#config-form Label {
    margin-top: 1;
    color: $text;
}

#config-form Input {
    margin-bottom: 1;
}

#generation-log, #deploy-log {
    height: 60%;
    border: round $accent;
    margin-bottom: 1;
}

#progress-bar {
    margin-bottom: 1;
}

.buttons {
    align: center bottom;
    height: auto;
}

.buttons Button {
    margin: 0 1;
}

#files-tabs {
    height: 80%;
}

#help-text {
    margin: 1;
    padding: 1;
}

#kubeconfig-selection-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#kubeconfig-selection-tabs {
    height: 60%;
    margin-bottom: 1;
}

#connection-test {
    border: round $accent;
    margin: 1;
    padding: 1;
}

#connection-status {
    margin: 1;
    padding: 0 1;
}

#namespace-selection-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#cluster-info {
    border: round $secondary;
    margin: 1;
    padding: 1;
}

#namespace-list {
    border: round $accent;
    margin: 1;
    padding: 1;
    height: 60%;
}

#namespace-list-selection {
    height: 80%;
    margin-bottom: 1;
}

#namespace-display {
    color: $accent;
    margin-bottom: 1;
    padding: 1;
    border: round $secondary;
}

#manual-namespace-dialog {
    align: center middle;
    width: 60%;
    height: 50%;
    border: thick $primary 80%;
    background: $surface;
}

#manual-namespace-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#manual-namespace-buttons {
    align: center bottom;
    height: auto;
    margin-top: 1;
}

#manual-namespace-buttons Button {
    margin: 0 1;
}

#project-namespace-dialog {
    align: center middle;
    width: 60%;
    height: 50%;
    border: thick $primary 80%;
    background: $surface;
}

#project-namespace-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#project-namespace-buttons {
    align: center bottom;
    height: auto;
    margin-top: 1;
}

#project-namespace-buttons Button {
    margin: 0 1;
}

#rancher-setup-title, #fleet-config-title, #release-selection-title, #configmap-gen-title, #view-configmaps-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#rancher-setup-content, #fleet-config-content, #release-selection-content, #configmap-gen-content, #view-configmaps-content {
    align: center middle;
    width: 90%;
    height: auto;
}

#target-namespace-info, #target-cluster-info, #view-namespace-info {
    text-align: center;
    color: $secondary;
    margin-bottom: 1;
}

#rancher-contexts-selection, #namespace-selection, #releases-selection {
    height: 60%;
    border: round $accent;
    margin-bottom: 1;
}

#rancher-namespaces-section {
    margin: 1 0;
}

#rancher-namespaces-table {
    height: 20;
    border: round $accent;
    margin-bottom: 1;
}

#fleet-config-tabs {
    height: 70%;
    margin-bottom: 1;
}

#configmap-preview, #yaml-preview {
    height: 70%;
    border: round $accent;
    margin-bottom: 1;
}

#settings-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#settings-content {
    align: center middle;
    width: 90%;
    height: auto;
}

.section-title {
    color: $secondary;
    margin: 1 0;
    text-style: bold;
}

.help-text {
    color: $text-muted;
    margin-bottom: 1;
}

.help-section {
    color: $text;
    margin: 1 0;
    padding: 1;
    border: round $secondary;
    background: $surface;
}

#settings-buttons {
    align: center bottom;
    height: auto;
    margin-top: 2;
}

#settings-buttons Button {
    margin: 0 1;
}

#directory-selection-dialog {
    align: center middle;
    width: 80%;
    height: 70%;
    border: thick $primary 80%;
    background: $surface;
    padding: 1;
}

#directory-selection-title {
    text-align: center;
    color: $primary;
    margin-bottom: 1;
}

#directory-selection-buttons {
    align: center bottom;
    height: auto;
    margin-top: 1;
}

#directory-selection-buttons Button {
    margin: 0 1;
}

#current-apps-dir, #current-int-dir, #apps-status, #int-status {
    margin: 1 0;
    padding: 0 1;
}
"""
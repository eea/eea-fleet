# EEA Fleet Configuration Generator

A terminal-based application for generating Rancher Fleet configurations for EEA Helm charts. This tool provides an interactive interface for managing Fleet deployments across multiple Kubernetes clusters with proper cluster-based organization.

## Overview

The EEA Fleet Configuration Generator is designed to simplify the process of creating and managing Fleet configurations for deployment across multiple Kubernetes clusters. It features a modern terminal user interface built with Textual and provides comprehensive support for EEA Helm charts with cluster-organized file management.

## Key Features

- **Interactive Fleet Configuration Generation**: Create fleet.yaml files with proper cluster targeting
- **Cluster-Based Organization**: Automatically organizes configurations by cluster for better management
- **EEA Helm Charts Support**: Pre-configured with comprehensive EEA Helm charts catalog
- **Advanced Cluster Targeting**: Multiple targeting strategies with intelligent fallback options
- **Real-time Helm Release Integration**: Extract configurations from existing deployed releases
- **ConfigMap Management**: Generate and deploy ConfigMaps with proper Kubernetes naming compliance
- **Rancher Integration**: Seamless integration with Rancher CLI for cluster management
- **Configuration Viewer**: View and manage existing Fleet configurations with tabbed interface
- **Persistent Chart Caching**: Fast application startup with cached chart information

## Installation

### Prerequisites

- Python 3.9 or higher
- Rancher CLI (properly configured with cluster access)
- kubectl CLI tool
- Active Kubernetes cluster connection

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd eea-fleet
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install and configure Rancher CLI** (if not already done):
   ```bash
   ./install-rancher-cli.sh
   rancher login https://your-rancher-server --token your-bearer-token
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

## How It Works

### Architecture Overview

The EEA Fleet Configuration Generator operates on a cluster-based file organization system:

- **Apps Directory**: `apps/<cluster>/<namespace>-<chart>/fleet.yaml`
- **Integration Directory**: `int/<cluster>/<namespace>-<chart>/<namespace>-<chart>-configmap.yaml`
- **Chart Cache**: `.eea-charts-cache.json` for fast application startup

### Core Components

1. **Cluster Context Management**: Automatically detects and manages Rancher cluster contexts
2. **Helm Release Scanner**: Extracts metadata from existing Helm releases using kubectl secrets
3. **Chart Repository Integration**: Dynamically loads EEA charts from the Helm repository
4. **Fleet Configuration Engine**: Generates compliant Fleet YAML configurations
5. **ConfigMap Generator**: Creates Kubernetes ConfigMaps with proper RFC 1123 naming

### Configuration Generation Process

1. **Cluster Detection**: Identifies current Rancher cluster context
2. **Chart Selection**: Offers charts from repository or existing deployments
3. **Metadata Extraction**: Retrieves chart versions and configurations from Helm secrets
4. **Directory Organization**: Creates cluster-specific directory structure
5. **File Generation**: Produces fleet.yaml and ConfigMap files
6. **Validation**: Ensures Kubernetes naming compliance and proper formatting

## Creating a New Fleet Configuration

### Method 1: From Helm Repository

1. **Start the application**:
   ```bash
   python main.py
   ```

2. **Select "Generate Fleet Configuration"** from the main menu

3. **Choose "Repository Mode"** to select from available charts

4. **Configure the application**:
   - **Application Name**: Enter a unique identifier for your application
   - **Target Namespace**: Specify the Kubernetes namespace for deployment
   - **Chart Selection**: Choose from the available EEA Helm charts
   - **Target Cluster**: Set the destination cluster name

5. **Customize Helm Values** (optional):
   ```yaml
   replicaCount: 2
   image:
     tag: "latest"
   resources:
     limits:
       memory: "512Mi"
       cpu: "500m"
   ```

6. **Generate Configuration**: The system will create:
   - `apps/<cluster>/<namespace>-<chart>/fleet.yaml`
   - `int/<cluster>/<namespace>-<chart>/<namespace>-<chart>-configmap.yaml`

### Method 2: From Existing Helm Release

1. **Select "Generate Fleet Configuration"** from the main menu

2. **Choose "Cluster Mode"** to work with deployed releases

3. **Select Namespace**: Choose from available namespaces in your cluster

4. **Select Helm Release**: Pick from existing deployed applications

5. **Configure Application Name**: The system will auto-populate based on the release

6. **Review Extracted Configuration**: The tool automatically extracts:
   - Chart version information
   - Current Helm values
   - Release metadata from Kubernetes secrets

7. **Generate Fleet Configuration**: Creates organized files with extracted metadata

### Configuration Structure

The generated fleet.yaml includes:

```yaml
namespace: <target-namespace>

helm:
  repo: https://eea.github.io/helm-charts/
  chart: <chart-name>
  version: <chart-version>
  releaseName: <application-name>
  valuesFrom:
    - configMapKeyRef:
        name: <namespace>-<chart>-config
        key: values.yaml

rolloutStrategy:
  maxUnavailable: "25%"
  maxUnavailablePartitions: "0"
  autoPartitionSize: "10%"

targetCustomizations:
  - clusterSelector:
      matchLabels:
        management.cattle.io/cluster-name: <cluster-name>
    helm:
      values:
        global:
          cluster: <cluster-name>
          environment: <namespace>
          deploymentType: fleet-managed
```

## Configuration Management

### Viewing Existing Configurations

1. **Select "View Existing Configurations"** from the main menu

2. **Browse Available Configurations**: Listed as `<cluster>/<namespace>-<chart>`

3. **View Configuration Details**: Select "view" to see:
   - **Fleet YAML Tab**: Complete Fleet configuration
   - **ConfigMap Tab**: Kubernetes ConfigMap with values

4. **Navigation**: Use the "Back" button to return to the configuration list

### Configuration Organization

Configurations are organized by cluster to support multi-cluster deployments:

```
apps/
├── production/
│   ├── web-nginx/
│   │   └── fleet.yaml
│   └── api-backend/
│       └── fleet.yaml
├── staging/
│   ├── web-nginx/
│   │   └── fleet.yaml
│   └── api-backend/
│       └── fleet.yaml
└── development/
    └── test-app/
        └── fleet.yaml

int/
├── production/
│   ├── web-nginx/
│   │   └── web-nginx-configmap.yaml
│   └── api-backend/
│       └── api-backend-configmap.yaml
├── staging/
│   ├── web-nginx/
│   │   └── web-nginx-configmap.yaml
│   └── api-backend/
│       └── api-backend-configmap.yaml
└── development/
    └── test-app/
        └── test-app-configmap.yaml
```

## Chart Management

### Chart Repository Integration

The application maintains a persistent cache of available EEA charts:

- **Fast Startup**: Uses cached chart information for immediate access
- **Repository Updates**: Refreshes chart catalog when browsing charts
- **Search Functionality**: Filter charts with real-time search
- **Version Information**: Displays latest chart versions and descriptions

### Supported Chart Categories

The EEA chart repository includes:

- **Web Applications**: Frontend and backend applications
- **Data Services**: Databases, storage, and data processing tools
- **Infrastructure**: Load balancers, ingress controllers, monitoring
- **Development Tools**: CI/CD, testing, and development utilities

## Advanced Features

### Helm Secret Metadata Extraction

The application can extract complete chart information from Kubernetes Helm release secrets:

```bash
# Automatically executes equivalent to:
kubectl get secret sh.helm.release.v1.<release-name>.v1 -n <namespace> -o json | \
  jq .data.release | tr -d '"' | base64 -d | base64 -d | gzip -d | jq '.chart.metadata'
```

### Cluster Context Management

- **Automatic Detection**: Identifies current Rancher cluster context
- **Context Switching**: Supports multiple cluster configurations
- **Persistent Settings**: Maintains cluster information across sessions

### RFC 1123 Compliance

All generated resource names comply with Kubernetes RFC 1123 DNS subdomain naming:

- Converts underscores to hyphens
- Ensures lowercase naming
- Validates length restrictions
- Prevents invalid character usage

## Configuration Files

### Application Settings

Settings are automatically managed and stored in the application's configuration system. Key settings include:

- **Directory Paths**: Location of apps and int directories
- **Cluster Context**: Current Rancher cluster information
- **Chart Cache**: Timestamp and version information for cached charts

### Fleet Configuration Customization

The generated Fleet configurations support:

- **Rollout Strategies**: Configurable deployment parameters
- **Cluster Targeting**: Multiple label-based targeting options
- **Global Values**: Cluster and environment information injection
- **Helm Options**: Advanced Helm deployment settings

## Troubleshooting

### Common Issues and Solutions

**Application won't start**:
- Verify Python 3.9+ is installed
- Check all dependencies are installed: `pip install -r requirements.txt`
- Ensure Rancher CLI is accessible: `rancher --version`

**No configurations appear**:
- Verify the apps directory contains cluster subdirectories
- Check cluster context: configurations are organized by cluster name
- Look in the correct cluster folder under apps/ and int/

**ConfigMap generation fails**:
- Ensure the int directory exists in the project root
- Verify cluster context is properly set
- Check namespace and chart name for RFC 1123 compliance

**Chart search not working**:
- Try refreshing charts from the Browse Charts screen
- Check internet connectivity for repository access
- Verify the chart cache file: `.eea-charts-cache.json`

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
EEA_DEBUG=true python main.py
```

Debug logs are written to `debug.log` and include:
- Cluster context detection
- Chart loading and caching
- File system operations
- Helm secret extraction
- Configuration generation steps

### Directory Structure Verification

Verify proper directory structure:

```bash
# Check main directories exist
ls -la apps/ int/

# Check cluster-specific directories
ls -la apps/your-cluster-name/
ls -la int/your-cluster-name/

# Verify configuration files
find apps/ -name "fleet.yaml" -ls
find int/ -name "*-configmap.yaml" -ls
```

## Development

### Project Structure

```
eea-fleet/
├── src/
│   ├── main.py              # Application entry point
│   ├── core.py              # Core functionality and utilities
│   ├── models.py            # Data models and constants
│   ├── screens.py           # TUI screen implementations
│   └── styles.py            # Textual CSS styling
├── apps/                    # Generated Fleet configurations (organized by cluster)
├── int/                     # Generated ConfigMaps (organized by cluster)
├── .eea-charts-cache.json   # Cached chart information
├── requirements.txt         # Python dependencies
├── main.py                  # Application launcher
└── README.md               # This documentation
```

### Extending the Application

**Adding New Chart Sources**:
- Modify the `get_eea_charts()` function in `core.py`
- Update the chart repository URL in `models.py`
- Test chart loading and caching functionality

**Customizing Fleet Generation**:
- Edit the `generate_fleet_yaml()` function in `core.py`
- Modify template structures in `models.py`
- Update cluster targeting logic for specific requirements

**Enhancing the User Interface**:
- Add new screens in `screens.py`
- Update styling in `styles.py`
- Modify the main menu structure for new features

## Support

For additional support:

1. **Check Debug Logs**: Enable debug mode to see detailed operation logs
2. **Verify Prerequisites**: Ensure all required tools are properly installed and configured
3. **Review Configuration**: Verify Rancher CLI and kubectl are working correctly
4. **Examine Directory Structure**: Ensure the cluster-based organization is properly maintained

The application is designed to provide clear error messages and detailed logging to facilitate troubleshooting and successful deployment management.
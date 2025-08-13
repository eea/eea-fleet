"""
Simplified data models and constants for EEA Fleet Configuration Generator
"""

from dataclasses import dataclass, field
import yaml
from typing import List, Dict, Optional
from pathlib import Path

# Configuration constants
SCRIPT_DIR = Path(__file__).parent.parent.absolute()
EEA_CHARTS_REPO = "https://github.com/eea/helm-charts"
EEA_HELM_REPO = "https://eea.github.io/helm-charts/"

EEA_CHARTS = [
    "advisory-board-backend", "advisory-board-frontend", "archiva", "archives", "bdr",
    "cachet", "casservice", "cdr", "centos7dev", "cluster-role-manager", "cm-share",
    "contreg", "converters", "databridge", "datadict", "eea-website-backend",
    "eea-website-frontend", "eggrepo", "eionet-gemet", "eionetldap", "elastic6",
    "elastic7", "emrt-esd", "emrt-necd", "eni-seis", "eunis", "fise-backend",
    "fise-frontend", "freshwater", "gitea", "glosreg", "haproxy", "iwlearn",
    "jenkins-master", "jenkins-slave", "keycloak-eea", "landscapeapi", "lcp",
    "lcp-frontend", "marine", "mars-backend", "mars-frontend", "memcached",
    "msd", "netcdf-utils", "opensearch", "opensearch-dashboards", "postfix",
    "postgres", "redis", "reportnet", "reportnet3", "rn-auth", "rn-ldap",
    "rn-postgresql", "sugarcube", "tika", "tralert", "varnish", "veeam-agent",
    "volto", "wise-backend", "wise-frontend"
]

@dataclass
class HelmRelease:
    name: str
    namespace: str
    chart: str
    version: str  # This is the release revision
    status: str
    chart_version: str = ""  # This is the actual chart version
    app_version: str = ""

@dataclass
class HelmConfig:
    file_path: str = ""
    content: str = ""
    releases: List['HelmRelease'] = field(default_factory=list)

@dataclass
class FleetYamlConfig:
    """Simplified Fleet YAML configuration."""
    rollout_strategy: Dict = field(default_factory=lambda: {
        "maxUnavailable": "25%",
        "maxUnavailablePartitions": "0",
        "autoPartitionSize": "10%"
    })

@dataclass
class FleetConfig:
    """Fleet configuration data."""
    app_name: str = ""
    namespace: str = ""
    chart_name: str = ""
    chart_version: str = ""
    helm_repo: str = EEA_HELM_REPO
    values: Dict = field(default_factory=dict)
    cluster_values: Dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    target_cluster: str = ""
    # Additional fields for existing releases
    is_existing_release: bool = False
    release_name: str = ""
    # Chart metadata from helm release secrets
    chart_metadata: Dict = field(default_factory=dict)
    # Fleet.yaml customization
    fleet_yaml_config: FleetYamlConfig = field(default_factory=FleetYamlConfig)

@dataclass
class RancherContextEntry:
    """Entry for Rancher context list display."""
    number: str
    cluster_name: str
    project_id: str
    project_name: str
    project_description: str = ""

@dataclass
class ExistingConfigMetadata:
    """Metadata for existing Fleet configurations."""
    app_name: str
    chart_name: str
    namespace: str
    target_cluster: str
    status: str

DEFAULT_FLEET_YAML_TEMPLATE = """
# Rancher Fleet Configuration
apiVersion: fleet.cattle.io/v1alpha1
kind: GitRepo
metadata:
  name: {app_name}
  namespace: fleet-default
spec:
  repo: {repo_url}
  branch: main
  paths:
  - charts/{chart_name}
  targets:
  - name: {target_name}
    clusterSelector:
      matchLabels:
        env: {environment}
    values:
      {values_yaml}
"""

DEFAULT_VALUES_TEMPLATE = """
# Helm Values for {chart_name}
replicaCount: 1

image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: "stable"

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 128Mi
"""

DEFAULT_CONFIGMAP_TEMPLATE = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: {app_name}-config
  namespace: {namespace}
data:
  values.yaml: |
{values_yaml_content}
"""

HELP_TEXT_CONTENT = """
# 🚀 EEA Fleet Configuration Generator - Help

## Overview
This tool helps you generate Rancher Fleet configurations for EEA Helm charts, providing an intuitive interface for:
- Setting up Rancher CLI connections
- Generating Fleet GitOps configurations
- Managing ConfigMaps for deployment
- Viewing existing configurations

## Prerequisites
Before using this tool, ensure you have:

### Required Tools
- **Rancher CLI**: Download from https://github.com/rancher/cli/releases (includes kubectl integration)
- **Python 3.9+**: With required dependencies

### Setup Steps
1. **Install Rancher CLI**:
   ```bash
   # On macOS
   brew install rancher-cli
   
   # On Linux
   wget https://github.com/rancher/cli/releases/latest/download/rancher-linux-amd64-v2.x.x.tar.gz
   tar -xzf rancher-linux-amd64-v2.x.x.tar.gz
   sudo mv rancher-v2.x.x/rancher /usr/local/bin/
   ```

2. **Login to Rancher**:
   ```bash
   rancher login https://your-rancher-server --token your-bearer-token
   ```

3. **Verify connection**:
   ```bash
   rancher context ls
   ```

## Main Features

### 🏗️ Rancher Setup
- Test and configure Rancher CLI connection
- List and switch between available contexts
- Verify cluster connectivity

### 🚀 Fleet Configuration
- Select target namespace and cluster
- Choose from available EEA Helm charts
- Configure chart values and dependencies
- Generate Fleet GitOps configurations

### 📦 Chart Management
- Browse all available EEA Helm charts
- Search and filter charts by category
- View chart documentation and requirements

### 🔍 Configuration Management
- View existing Fleet configurations
- Edit and update configurations
- Deploy ConfigMaps to clusters

## Usage Workflow

### 1. Initial Setup
- Start with "Setup Rancher Connection"
- Verify your CLI is properly configured
- Select your target cluster context

### 2. Generate Configuration
- Use "Generate Fleet Configuration"
- Follow the step-by-step wizard:
  1. Select target namespace
  2. Choose EEA Helm chart
  3. Configure chart values
  4. Review generated configuration
  5. Deploy ConfigMap

### 3. Monitor Deployment
- View generated files (fleet.yaml, values.yaml)
- Monitor deployment logs
- Verify configuration in Rancher UI

## Advanced Features

### Custom Values
You can provide custom Helm values in YAML format:
```yaml
replicaCount: 3
image:
  tag: "v1.2.3"
resources:
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### Multi-Environment Support
Configure different values for different environments:
- Development: Lower resource limits
- Staging: Production-like setup
- Production: Full resource allocation

### Dependency Management
Some charts have dependencies that will be automatically configured:
- Database requirements
- Storage dependencies
- Network policies

## Troubleshooting

### Common Issues

**1. Rancher CLI not found**
- Ensure Rancher CLI is installed and in PATH
- Verify with: `rancher --version`

**2. Authentication errors**
- Check your bearer token is valid
- Re-login with: `rancher login`

**3. Cluster connectivity**
- Verify kubectl access: `rancher kubectl cluster-info`
- Check context: `rancher context current`

**4. Namespace issues**
- Ensure target namespace exists
- Verify RBAC permissions

### Getting Help
- Use the built-in validation and error messages
- Check Rancher server logs for deployment issues
- Verify chart availability in EEA repository
- Review Fleet documentation: https://fleet.rancher.io/

## Keyboard Shortcuts

- **Escape**: Go back to previous screen
- **Ctrl+R**: Refresh current view
- **Ctrl+S**: Search/filter items
- **Ctrl+G**: Generate configuration
- **Ctrl+D**: Deploy configuration
- **Ctrl+L**: Login to Rancher

## Support
For issues and feature requests:
- Check the EEA Helm Charts repository
- Review Rancher Fleet documentation
- Contact your cluster administrator
"""

# Legacy functions removed - functionality moved to core.py
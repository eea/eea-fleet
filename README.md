# eea-fleet

This application is designed for deploying applications to Rancher2. It provides fleet-specific configurations for managing and deploying Helm charts in a Rancher environment.

## Overview

The eea-fleet app handles the deployment and management of applications within Rancher2 clusters. It provides streamlined configuration management for fleet deployments.

## Generating New Apps

To generate a new application, use the utility application located in the `utils/` directory. This tool provides an interactive interface for creating new app configurations that are compatible with the fleet deployment system.

### Creating a New Configuration

1. **Navigate to the utils directory**:
   ```bash
   cd utils/
   ```

2. **Install dependencies** (if not already done):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the configuration generator**:
   ```bash
   python main.py
   ```

4. **Follow the interactive prompts**:
   - Select "Generate Fleet Configuration" from the main menu
   - Choose between "Repository Mode" (select from available EEA Helm charts) or "Cluster Mode" (extract from existing deployments)
   - Configure your application settings:
     - **Application Name**: Unique identifier for your app
     - **Target Namespace**: Kubernetes namespace for deployment
     - **Chart Selection**: Choose from available EEA Helm charts
     - **Target Cluster**: Destination cluster name
   - Customize Helm values as needed

5. **Generated files**:
   The tool will create organized configuration files:
   - `apps/<cluster>/<namespace>-<chart>/fleet.yaml` - Fleet deployment configuration
   - `int/<cluster>/<namespace>-<chart>/<namespace>-<chart>-configmap.yaml` - ConfigMap with Helm values

The generated configurations are automatically organized by cluster and follow Rancher Fleet best practices for multi-cluster deployments.

> **Note**: ConfigMap files in the `int/` directory contain environment-specific configurations and should be excluded from version control to maintain security and flexibility across different deployment environments.

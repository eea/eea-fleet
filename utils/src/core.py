"""
EEA Fleet Configuration Generator - Core Module

Consolidated business logic combining all services into simple functions with module-level state.
Eliminates complex context management and service abstractions.
"""

import json
import yaml
import subprocess
import tempfile
import logging
import traceback
import inspect
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict  # noqa: F401 (kept for potential future use)
import atexit

from .models import (
    HelmRelease, FleetConfig, RancherContextEntry,
    EEA_CHARTS, EEA_HELM_REPO,
    DEFAULT_VALUES_TEMPLATE
)

# Module-level global state (replaces complex context.py system)
_current_cluster_context: Optional[str] = None
_current_cluster_id: Optional[str] = None 
_current_cluster_name: Optional[str] = None
_apps_dir: Path = Path("apps")
_int_dir: Path = Path("int")
_settings: Dict[str, Any] = {}
_debug_log: Optional[logging.Logger] = None
_cached_charts: List[str] = []
_charts_cache_timestamp: Optional[datetime] = None
_charts_cache_duration = 3600  # Cache for 1 hour
_charts_cache_file = Path(".eea-charts-cache.json")  # Persistent cache file

# Initialize debug logging
def _setup_debug_logging():
    """Setup simple debug logging to file without duplication."""
    global _debug_log
    if _debug_log is None:
        _debug_log = logging.getLogger("eea_fleet_core")
        _debug_log.setLevel(logging.DEBUG)
        # Prevent propagation to parent loggers to avoid duplicates
        _debug_log.propagate = False
        
        # Clear any existing handlers
        _debug_log.handlers.clear()
        
        handler = logging.FileHandler("debug.log")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        )
        handler.setFormatter(formatter)
        _debug_log.addHandler(handler)

_setup_debug_logging()

def log_error(context: str, error: Exception, additional_info: Dict = None):
    """Simple error logging without complex error handler class."""
    # Capture caller info (the function that invoked log_error)
    frame = inspect.stack()[1]
    caller_info = {
        "file": Path(frame.filename).name,
        "line": frame.lineno,
        "function": frame.function,
    }

    error_info = {
        "context": context,
        "error": str(error),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.now().isoformat(),
        **caller_info,
    }
    if additional_info:
        error_info.update(additional_info)

    # stacklevel=2 makes the log record point at the caller of this helper
    _debug_log.error(f"ERROR in {context}: {error_info}", stacklevel=2, exc_info=True)

def log_debug(context: str, message: str):
    """Simple debug logging without duplication."""
    _debug_log.debug(message, stacklevel=2)

def log_chart_debug(chart_obj, context: str = "chart_debug"):
    """Debug log chart object with key-value pairs."""
    if chart_obj is None:
        log_debug(context, "Chart object is None")
        return
        
    if hasattr(chart_obj, '__dict__'):
        chart_data = chart_obj.__dict__
    else:
        chart_data = str(chart_obj)
    
    log_debug(context, f"Chart object: {chart_data}")
    
    # Log individual key-value pairs for charts
    if isinstance(chart_data, dict):
        for key, value in chart_data.items():
            log_debug(context, f"  {key}: {value}")

def log_fleet_context_debug(context: str = "fleet_context_debug"):
    """Debug log current fleet context with key-value pairs."""
    try:
        context_info, cluster_id, cluster_name = get_current_rancher_context()
        
        log_debug(context, "Fleet Context:")
        log_debug(context, f"  rancher_context: {context_info}")
        log_debug(context, f"  cluster_id: {cluster_id}")
        log_debug(context, f"  cluster_name: {cluster_name}")
        log_debug(context, f"  apps_dir: {_apps_dir}")
        log_debug(context, f"  int_dir: {_int_dir}")
        
        # Also log current settings
        log_debug(context, "Settings:")
        for key, value in _settings.items():
            log_debug(context, f"  {key}: {value}")
            
    except Exception as e:
        log_debug(context, f"Error getting fleet context: {str(e)}")

# ==============================================================================
# SETTINGS AND CONFIGURATION FUNCTIONS
# ==============================================================================

def load_settings() -> Dict[str, Any]:
    """Load application settings from file."""
    global _settings
    try:
        config_file = Path(".eea-fleet-config.json")
        if config_file.exists():
            _settings = json.loads(config_file.read_text())
            return _settings
    except Exception as e:
        log_error("load_settings", e)
    return {}

def save_settings(settings: Dict[str, Any]) -> bool:
    """Save application settings to file, merging with existing settings."""
    global _settings
    try:
        # Merge new settings with existing ones instead of replacing
        _settings.update(settings)
        config_file = Path(".eea-fleet-config.json")
        config_file.write_text(json.dumps(_settings, indent=2))
        return True
    except Exception as e:
        log_error("save_settings", e)
        return False

def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value."""
    return _settings.get(key, default)

def set_setting(key: str, value: Any) -> None:
    """Set a setting value."""
    global _settings
    _settings[key] = value

def show_advanced_options() -> bool:
    """Check if advanced options should be shown."""
    return get_setting("show_advanced", False)

def initialize_directories() -> bool:
    """Initialize apps and int directories."""
    global _apps_dir, _int_dir
    try:
        from .models import SCRIPT_DIR
        
        apps_dir = get_setting("apps_dir", "apps")
        int_dir = get_setting("int_dir", "int")
        
        # Ensure paths are absolute - resolve relative to SCRIPT_DIR
        if not Path(apps_dir).is_absolute():
            _apps_dir = SCRIPT_DIR / apps_dir
        else:
            _apps_dir = Path(apps_dir)
            
        if not Path(int_dir).is_absolute():
            _int_dir = SCRIPT_DIR / int_dir
        else:
            _int_dir = Path(int_dir)
        
        _apps_dir.mkdir(parents=True, exist_ok=True)
        _int_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect current rancher context if not already set
        if not get_current_rancher_context()[0]:
            log_debug("initialize_directories", "Auto-detecting rancher context...")
            detect_and_set_current_rancher_context()
        
        return True
    except Exception as e:
        log_error("initialize_directories", e)
        return False

def get_apps_dir() -> Path:
    """Get apps directory path."""
    return _apps_dir

def get_int_dir() -> Path:
    """Get int directory path."""
    return _int_dir

# ==============================================================================
# RANCHER FUNCTIONS
# ==============================================================================

def get_current_rancher_context() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Get current Rancher context information."""
    global _current_cluster_context, _current_cluster_id, _current_cluster_name
    if _current_cluster_context:
        return _current_cluster_context, _current_cluster_id, _current_cluster_name
    
    # Load from settings
    _current_cluster_context = get_setting("current_cluster_context")
    _current_cluster_id = get_setting("current_cluster_id") 
    _current_cluster_name = get_setting("current_cluster_name")
    
    return _current_cluster_context, _current_cluster_id, _current_cluster_name

def set_rancher_context(context: str, cluster_id: str, cluster_name: str) -> None:
    """Set current Rancher context."""
    global _current_cluster_context, _current_cluster_id, _current_cluster_name
    _current_cluster_context = context
    _current_cluster_id = cluster_id
    _current_cluster_name = cluster_name
    
    set_setting("current_cluster_context", context)
    set_setting("current_cluster_id", cluster_id)
    set_setting("current_cluster_name", cluster_name)
    # Save the current settings to file
    save_settings({})

def detect_and_set_current_rancher_context() -> bool:
    """Automatically detect and set the current rancher context."""
    try:
        # Get current context from rancher
        success, output = run_rancher_command(["context", "current"])
        if not success:
            log_debug("detect_rancher_context", f"Failed to get current rancher context: {output}")
            return False
            
        # Parse the output to extract context information
        lines = output.strip().split('\n')
        cluster_name = None
        project_name = None
        
        # Look for format: "Cluster:02pre Project:Plone websites"
        for line in lines:
            if line.startswith("Cluster:"):
                # Extract cluster and project from the line
                parts = line.split(" Project:")
                if len(parts) == 2:
                    cluster_name = parts[0].replace("Cluster:", "").strip()
                    project_name = parts[1].strip()
                    break
        
        if not cluster_name or not project_name:
            log_debug("detect_rancher_context", f"Could not parse cluster/project from: {output}")
            return False
            
        # Get the actual cluster ID from rancher cluster ls
        cluster_id = _get_cluster_id_from_rancher(cluster_name)
        if not cluster_id:
            log_debug("detect_rancher_context", f"Could not get cluster ID for cluster: {cluster_name}")
            # Fallback to project name if cluster ID lookup fails
            cluster_id = project_name
            
        # Create context string and set the context information
        current_context = f"{cluster_name}:{project_name}"
        set_rancher_context(current_context, cluster_id, cluster_name)
        log_debug("detect_rancher_context", f"Auto-detected rancher context: {current_context} -> cluster: {cluster_name}, cluster_id: {cluster_id}, project: {project_name}")
        return True
            
    except Exception as e:
        log_error("detect_rancher_context", e)
        return False

def _get_cluster_id_from_rancher(cluster_name: str) -> Optional[str]:
    """Get the actual cluster ID from rancher cluster ls command."""
    try:
        success, output = run_rancher_command(["cluster", "ls", "--format", "json"])
        if not success:
            log_debug("get_cluster_id", f"Failed to get cluster list: {output}")
            return None
            
        # Parse the multiline JSON output
        lines = output.strip().split('\n')
        for line in lines:
            if line.strip():
                try:
                    cluster_data = json.loads(line)
                    # Check if this is the current cluster by looking for "Current":"*" 
                    # or matching cluster name
                    if (cluster_data.get("Current") == "*" or 
                        (cluster_data.get("Cluster", {}).get("name") == cluster_name)):
                        cluster_id = cluster_data.get("ID")
                        if cluster_id:
                            log_debug("get_cluster_id", f"Found cluster ID: {cluster_id} for cluster: {cluster_name}")
                            return cluster_id
                except json.JSONDecodeError as e:
                    log_debug("get_cluster_id", f"Failed to parse JSON line: {line} - Error: {e}")
                    continue
                    
        log_debug("get_cluster_id", f"No cluster ID found for cluster: {cluster_name}")
        return None
        
    except Exception as e:
        log_error("get_cluster_id", e)
        return None

def run_rancher_command(args: List[str], timeout: int = 30) -> Tuple[bool, str]:
    """Execute rancher command and return success status and output."""
    try:
        cmd = ["rancher"] + args
        log_debug("run_rancher_command", f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            check=False
        )
        
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        log_debug("run_rancher_command", f"Success: {success}, Output: {output[:200]}")
        return success, output
        
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        log_error("run_rancher_command", e, {"args": args})
        return False, str(e)

def get_rancher_projects() -> List[RancherContextEntry]:
    """Get available Rancher projects using pexpect."""
    import pexpect
    import re
    
    try:
        child = pexpect.spawn("rancher context switch", encoding='utf-8', timeout=10)
        child.expect("Select a Project:")
        output = child.before
        child.sendcontrol('c')
        child.close()
        
        lines = output.strip().splitlines()
        project_lines = [line for line in lines if re.match(r"^\d+\s", line)]
        
        projects = []
        for line in project_lines:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 5:
                projects.append(RancherContextEntry(
                    number=parts[0],
                    cluster_name=parts[1],
                    project_id=parts[2],
                    project_name=parts[3],
                    project_description=parts[4]
                ))
        
        log_debug("get_rancher_projects", f"Found {len(projects)} projects")
        return projects
    except pexpect.TIMEOUT:
        log_error("get_rancher_projects", Exception("Timeout waiting for rancher context switch"))
        return []
    except pexpect.EOF:
        log_error("get_rancher_projects", Exception("Unexpected EOF from rancher command"))
        return []
    except Exception as e:
        log_error("get_rancher_projects", e)
        return []

# Keep backward compatibility alias
def list_rancher_contexts() -> List[RancherContextEntry]:
    """List available Rancher contexts (compatibility alias)."""
    return get_rancher_projects()

def switch_rancher_context(project_id: str) -> bool:
    """Switch to a different Rancher context using project ID directly."""
    try:
        # Use direct command with project_id from get_rancher_projects
        success, output = run_rancher_command(["context", "switch", project_id])
        
        if success:
            # Validate the switch by checking current context
            success, output = run_rancher_command(["context", "current"])
            if success and output.strip():
                # Update global context state
                # Parse "Cluster:name Project:name" format
                if "Cluster:" in output and "Project:" in output:
                    parts = output.strip().split()
                    cluster_name = parts[0].replace("Cluster:", "")
                    project_name = " ".join(parts[1:]).replace("Project:", "")
                    
                    # Get project details for complete context info
                    projects = get_rancher_projects()
                    for project in projects:
                        if project.project_id == project_id:
                            set_rancher_context(cluster_name, project.project_id, project.cluster_name)
                            break
                    
                    log_debug("switch_rancher_context", f"Switched to {cluster_name}/{project_name}")
                    return True
            
            return False
        else:
            log_error("switch_rancher_context", Exception(f"Failed to switch to project ID {project_id}: {output}"))
            return False
                
    except Exception as e:
        log_error("switch_rancher_context", e, {"project_id": project_id})
        return False

# Module-level kubeconfig tracking
_current_kubeconfig_path: Optional[str] = None

def generate_temp_kubeconfig() -> Optional[str]:
    """Generate temporary kubeconfig from current Rancher context."""
    try:
        import tempfile
        
        # Generate kubeconfig content using rancher
        success, output = run_rancher_command(["kubectl", "config", "view", "--raw"])
        if not success or not output.strip():
            log_error("generate_temp_kubeconfig", Exception("Failed to get kubeconfig from rancher"))
            return None
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(output)
            temp_path = f.name
        
        log_debug("generate_temp_kubeconfig", f"Created temporary kubeconfig: {temp_path}")
        return temp_path
        
    except Exception as e:
        log_error("generate_temp_kubeconfig", e)
        return None

def set_current_kubeconfig(kubeconfig_path: str) -> None:
    """Set current kubeconfig path globally."""
    global _current_kubeconfig_path
    
    # Clean up previous kubeconfig
    if _current_kubeconfig_path and Path(_current_kubeconfig_path).exists():
        cleanup_temp_kubeconfig(_current_kubeconfig_path)
    
    _current_kubeconfig_path = kubeconfig_path
    log_debug("set_current_kubeconfig", f"Set kubeconfig: {kubeconfig_path}")

def get_current_kubeconfig() -> Optional[str]:
    """Get current kubeconfig path."""
    return _current_kubeconfig_path

def cleanup_temp_kubeconfig(kubeconfig_path: str) -> None:
    """Clean up temporary kubeconfig file."""
    try:
        if kubeconfig_path and Path(kubeconfig_path).exists():
            Path(kubeconfig_path).unlink()
            log_debug("cleanup_temp_kubeconfig", f"Cleaned up: {kubeconfig_path}")
    except Exception as e:
        log_error("cleanup_temp_kubeconfig", e, {"path": kubeconfig_path})

# Keep old function for compatibility
def generate_kubeconfig() -> Optional[str]:
    """Generate temporary kubeconfig (compatibility alias)."""
    return generate_temp_kubeconfig()

# ==============================================================================
# KUBERNETES FUNCTIONS 
# ==============================================================================

def list_namespaces() -> List[str]:
    """List accessible namespaces using Rancher CLI."""
    try:
        success, output = run_rancher_command(["namespaces", "ls", "--format", "json"])
        if success and output.strip():
            import json
            try:
                namespaces = []
                # Parse each line as a separate JSON object
                lines = output.strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            data = json.loads(line.strip())
                            # Extract namespace name from different possible structures
                            if isinstance(data, dict):
                                # Check for direct name field
                                if "name" in data:
                                    namespaces.append(data["name"])
                                # Check for ID field (Rancher format)
                                elif "ID" in data:
                                    namespaces.append(data["ID"])
                                # Check for nested Namespace.id field
                                elif "Namespace" in data and isinstance(data["Namespace"], dict):
                                    if "id" in data["Namespace"]:
                                        namespaces.append(data["Namespace"]["id"])
                        except json.JSONDecodeError:
                            # Skip malformed JSON lines
                            continue
                
                log_debug("list_namespaces", f"Found {len(namespaces)} namespaces via Rancher")
                return namespaces
            except Exception as e:
                log_error("list_namespaces", e, {"output": output[:200]})
                return []
        return []
    except Exception as e:
        log_error("list_namespaces", e)
        return []

# Namespace creation removed - namespaces should exist in Rancher beforehand

def namespace_exists(namespace: str) -> bool:
    """Check if namespace exists using Rancher namespaces list."""
    try:
        namespaces = list_namespaces()
        exists = namespace in namespaces
        log_debug("namespace_exists", f"Namespace '{namespace}' exists: {exists}")
        return exists
    except Exception as e:
        log_error("namespace_exists", e, {"namespace": namespace})
        return False

def validate_namespace_access(namespace: str) -> Tuple[bool, str]:
    """Validate that namespace exists and is accessible via Rancher."""
    try:
        if not namespace_exists(namespace):
            return False, f"Namespace '{namespace}' does not exist in current Rancher context"
        
        # If namespace is listed by Rancher, it should be accessible
        return True, f"Namespace '{namespace}' is accessible"
            
    except Exception as e:
        log_error("validate_namespace_access", e, {"namespace": namespace})
        return False, str(e)

# ConfigMap listing removed - not needed for Fleet configuration generation

# ==============================================================================
# HELM FUNCTIONS
# ==============================================================================

def run_helm_with_kubeconfig(args: List[str], kubeconfig_path: str) -> Tuple[bool, str]:
    """Execute helm command with specific kubeconfig."""
    try:
        import subprocess
        import os
        
        cmd = ["helm"] + args
        env = os.environ.copy()
        env['KUBECONFIG'] = kubeconfig_path
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30,
            env=env,
            check=False
        )
        
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        log_debug("run_helm_with_kubeconfig", f"Helm command: {' '.join(cmd)}, Success: {success}")
        return success, output
        
    except Exception as e:
        log_error("run_helm_with_kubeconfig", e)
        return False, str(e)

def get_helm_release_secret_metadata(release_name: str, namespace: str, kubeconfig_path: str) -> Dict[str, str]:
    """Extract chart metadata from helm release secret."""
    try:
        # Get the secret name for the helm release
        secret_name = f"sh.helm.release.v1.{release_name}.v1"
        log_debug("get_helm_release_secret_metadata", f"Extracting metadata for release {release_name} from secret {secret_name}")
        
        # Try to get the secret using kubectl
        kubectl_args = ["kubectl", "get", "secret", secret_name, "-n", namespace, "-o", "json"]
        log_debug("get_helm_release_secret_metadata", f"Running kubectl command: {' '.join(kubectl_args)}")
        success, output = run_rancher_command(kubectl_args)
        
        if not success or not output.strip():
            log_debug("get_helm_release_secret_metadata", f"Failed to get secret {secret_name} in namespace {namespace}: {output}")
            return {}
        
        log_debug("get_helm_release_secret_metadata", f"Successfully retrieved secret {secret_name}, output size: {len(output)} bytes")
        
        try:
            secret_data = json.loads(output)
            log_debug("get_helm_release_secret_metadata", f"Secret JSON parsed successfully, data keys: {list(secret_data.keys())}")
            
            data_section = secret_data.get("data", {})
            log_debug("get_helm_release_secret_metadata", f"Secret data section keys: {list(data_section.keys())}")
            
            release_data = data_section.get("release", "")
            
            if not release_data:
                log_debug("get_helm_release_secret_metadata", f"No 'release' key found in secret {secret_name} data section")
                return {}
            
            log_debug("get_helm_release_secret_metadata", f"Release data found, encoded size: {len(release_data)} bytes")
            
            # Decode the release data (base64 -> base64 -> gzip)
            import base64
            import gzip
            import binascii
            
            # First base64 decode
            log_debug("get_helm_release_secret_metadata", "Starting first base64 decode...")
            decoded_once = base64.b64decode(release_data).decode('utf-8')
            log_debug("get_helm_release_secret_metadata", f"First decode completed, size: {len(decoded_once)} bytes")
            
            # Remove quotes if present
            if decoded_once.startswith('"') and decoded_once.endswith('"'):
                decoded_once = decoded_once[1:-1]
                log_debug("get_helm_release_secret_metadata", "Removed surrounding quotes from decoded data")
            
            # Second base64 decode  
            log_debug("get_helm_release_secret_metadata", "Starting second base64 decode...")
            decoded_twice = base64.b64decode(decoded_once)
            log_debug("get_helm_release_secret_metadata", f"Second decode completed, compressed size: {len(decoded_twice)} bytes")
            
            # Gzip decompress
            log_debug("get_helm_release_secret_metadata", "Starting gzip decompression...")
            decompressed = gzip.decompress(decoded_twice).decode('utf-8')
            log_debug("get_helm_release_secret_metadata", f"Gzip decompression completed, final size: {len(decompressed)} bytes")
            
            # Parse the JSON
            log_debug("get_helm_release_secret_metadata", "Parsing final JSON...")
            release_json = json.loads(decompressed)
            log_debug("get_helm_release_secret_metadata", f"Release JSON parsed, top-level keys: {list(release_json.keys())}")
            
            # Extract chart metadata
            chart_section = release_json.get("chart", {})
            log_debug("get_helm_release_secret_metadata", f"Chart section keys: {list(chart_section.keys()) if isinstance(chart_section, dict) else 'not a dict'}")
            
            chart_metadata = chart_section.get("metadata", {}) if isinstance(chart_section, dict) else {}
            log_debug("get_helm_release_secret_metadata", f"Chart metadata keys: {list(chart_metadata.keys()) if isinstance(chart_metadata, dict) else 'not a dict'}")
            
            result = {
                "name": chart_metadata.get("name", ""),
                "version": chart_metadata.get("version", ""), 
                "appVersion": chart_metadata.get("appVersion", ""),
                "description": chart_metadata.get("description", "")
            }
            
            log_debug("get_helm_release_secret_metadata", f"Extracted metadata for {release_name}: {result}")
            return result
            
        except json.JSONDecodeError as e:
            log_debug("get_helm_release_secret_metadata", f"JSON decode error for {release_name}: {str(e)}")
            return {}
        except (binascii.Error, ValueError) as e:
            log_debug("get_helm_release_secret_metadata", f"Base64 decode error for {release_name}: {str(e)}")
            return {}
        except gzip.BadGzipFile as e:
            log_debug("get_helm_release_secret_metadata", f"Gzip decode error for {release_name}: {str(e)}")
            return {}
        except Exception as e:
            log_debug("get_helm_release_secret_metadata", f"Unexpected error decoding secret data for {release_name}: {str(e)}")
            return {}
        
    except Exception as e:
        log_error("get_helm_release_secret_metadata", e, {"release_name": release_name, "namespace": namespace})
        return {}

def list_helm_releases(namespace: str = None) -> List[HelmRelease]:
    """List Helm releases using helm list and helm get metadata commands, with secret metadata extraction."""
    try:
        # Get or generate kubeconfig
        kubeconfig_path = get_current_kubeconfig()
        if not kubeconfig_path:
            kubeconfig_path = generate_temp_kubeconfig()
            if not kubeconfig_path:
                log_error("list_helm_releases", Exception("No kubeconfig available"))
                return []
            set_current_kubeconfig(kubeconfig_path)
        
        # Use helm list command to get basic release info
        helm_args = ["list", "--output", "json"]
        if namespace:
            helm_args.extend(["-n", namespace])
        else:
            helm_args.append("--all-namespaces")
        
        success, output = run_helm_with_kubeconfig(helm_args, kubeconfig_path)
        
        if not success or not output.strip():
            return []
        
        releases = []
        data = json.loads(output)
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    release_name = item.get("name", "")
                    release_namespace = item.get("namespace", "")
                    release_revision = str(item.get("revision", ""))
                    release_status = item.get("status", "")
                    
                    # Get detailed metadata from helm get metadata
                    metadata_args = ["get", "metadata", release_name, "-n", release_namespace, "--output", "json"]
                    metadata_success, metadata_output = run_helm_with_kubeconfig(metadata_args, kubeconfig_path)
                    
                    chart_name = ""
                    chart_version = ""
                    app_version = ""
                    
                    if metadata_success and metadata_output.strip():
                        try:
                            metadata = json.loads(metadata_output)
                            chart_name = metadata.get("chart", "")
                            chart_version = metadata.get("version", "")
                            app_version = metadata.get("appVersion", "")
                        except json.JSONDecodeError:
                            log_debug("list_helm_releases", f"Failed to parse metadata JSON for {release_name}")
                            # Fallback to chart field from helm list if metadata parsing fails
                            chart_name = item.get("chart", "")
                    else:
                        # Fallback to chart field from helm list if metadata command fails
                        chart_name = item.get("chart", "")
                        log_debug("list_helm_releases", f"Failed to get metadata for {release_name}: {metadata_output}")
                    
                    # Try to get additional metadata from release secret if standard methods didn't work well
                    if not chart_version or not app_version:
                        secret_metadata = get_helm_release_secret_metadata(release_name, release_namespace, kubeconfig_path)
                        if secret_metadata:
                            chart_name = secret_metadata.get("name", "") or chart_name
                            chart_version = secret_metadata.get("version", "") or chart_version  
                            app_version = secret_metadata.get("appVersion", "") or app_version
                    
                    releases.append(HelmRelease(
                        name=release_name,
                        namespace=release_namespace,
                        chart=chart_name,
                        version=release_revision,
                        status=release_status,
                        chart_version=chart_version,
                        app_version=app_version
                    ))
        
        log_debug("list_helm_releases", f"Found {len(releases)} helm releases")
        return releases
        
    except Exception as e:
        log_error("list_helm_releases", e, {"namespace": namespace})
        return []

def get_helm_release_values(release_name: str, namespace: str) -> Dict[str, Any]:
    """Get values for a Helm release using helm get values."""
    try:
        # Get or generate kubeconfig
        kubeconfig_path = get_current_kubeconfig()
        if not kubeconfig_path:
            kubeconfig_path = generate_temp_kubeconfig()
            if not kubeconfig_path:
                return {}
            set_current_kubeconfig(kubeconfig_path)
        
        # Try JSON first
        helm_args_json = ["get", "values", release_name, "-n", namespace, "--output", "json"]
        success, output = run_helm_with_kubeconfig(helm_args_json, kubeconfig_path)

        def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
            # Some helm versions may prepend warnings; try to isolate JSON payload
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Heuristic: find first '{' and last '}'
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1 and end > start:
                    try:
                        return json.loads(text[start:end + 1])
                    except Exception:
                        return None
                return None

        if success and output.strip():
            parsed = _try_parse_json(output)
            if parsed is not None:
                return parsed

        # Fallback to YAML output parsing when JSON isn't available or helm returns unmarshal errors
        helm_args_yaml = ["get", "values", release_name, "-n", namespace, "--output", "yaml"]
        success_yaml, output_yaml = run_helm_with_kubeconfig(helm_args_yaml, kubeconfig_path)
        if success_yaml and output_yaml.strip():
            try:
                data = yaml.safe_load(output_yaml) or {}
                if isinstance(data, dict):
                    return data
                # Helm may print plain text when no values set; normalize to {}
                return {}
            except Exception as e:
                log_error("get_helm_release_values_yaml_parse", e, {"snippet": output_yaml[:200]})
                return {}

        # As a last resort, return empty dict to avoid crashing the UI
        if not success:
            log_error("get_helm_release_values", Exception("helm get values failed"), {"stderr": output[:200]})
        return {}
    except Exception as e:
        log_error("get_helm_release_values", e, {"release_name": release_name, "namespace": namespace})
        return {}

def create_configmap_via_kubectl(name: str, namespace: str, data: Dict[str, str]) -> bool:
    """Create ConfigMap via rancher kubectl command."""
    try:
        # Create ConfigMap YAML
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "data": data
        }
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(configmap, f)
            temp_file = f.name
        
        try:
            # Use rancher kubectl apply
            success, output = run_rancher_command(["kubectl", "apply", "-f", temp_file])
            if not success:
                log_error("create_configmap_via_kubectl", 
                         Exception(f"rancher kubectl apply failed: {output}"))
            
            return success
        finally:
            Path(temp_file).unlink(missing_ok=True)
            
    except Exception as e:
        log_error("create_configmap_via_kubectl", e, {"name": name, "namespace": namespace})
        return False

# Keep old function name for compatibility
def create_configmap(name: str, namespace: str, data: Dict[str, str]) -> bool:
    """Create ConfigMap (compatibility alias)."""
    return create_configmap_via_kubectl(name, namespace, data)

# ==============================================================================
# CHART FUNCTIONS
# ==============================================================================

def fetch_charts_from_helm_repo() -> List[str]:
    """Fetch available charts from EEA helm repository."""
    try:
        log_debug("fetch_charts_from_helm_repo", f"Fetching charts from {EEA_HELM_REPO}")
        
        # Add EEA helm repo if not already added
        add_repo_success, add_repo_output = run_helm_command(
            ["repo", "add", "eea", EEA_HELM_REPO, "--force-update"]
        )
        if not add_repo_success:
            log_debug("fetch_charts_from_helm_repo", f"Failed to add repo: {add_repo_output}")
            return []
        
        # Update helm repos
        update_success, update_output = run_helm_command(["repo", "update"])
        if not update_success:
            log_debug("fetch_charts_from_helm_repo", f"Failed to update repos: {update_output}")
            return []
        
        # Search for charts in the EEA repo
        search_success, search_output = run_helm_command(
            ["search", "repo", "eea/", "--output", "json"]
        )
        if not search_success or not search_output.strip():
            log_debug("fetch_charts_from_helm_repo", f"Failed to search repo: {search_output}")
            return []
        
        # Parse the JSON output
        try:
            charts_data = json.loads(search_output)
            if not isinstance(charts_data, list):
                log_debug("fetch_charts_from_helm_repo", "Search output is not a list")
                return []
            
            charts = []
            for chart_info in charts_data:
                if isinstance(chart_info, dict) and "name" in chart_info:
                    # Extract chart name (remove "eea/" prefix)
                    full_name = chart_info["name"]
                    if full_name.startswith("eea/"):
                        chart_name = full_name[4:]  # Remove "eea/" prefix
                        charts.append(chart_name)
            
            log_debug("fetch_charts_from_helm_repo", f"Successfully fetched {len(charts)} charts from repo")
            return sorted(charts)
            
        except json.JSONDecodeError as e:
            log_debug("fetch_charts_from_helm_repo", f"Failed to parse search output JSON: {e}")
            return []
        
    except Exception as e:
        log_error("fetch_charts_from_helm_repo", e)
        return []

def run_helm_command(args: List[str]) -> Tuple[bool, str]:
    """Execute helm command without kubeconfig (for repo operations)."""
    try:
        cmd = ["helm"] + args
        log_debug("run_helm_command", f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30,
            check=False
        )
        
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        log_debug("run_helm_command", f"Success: {success}, Output: {output[:200]}")
        return success, output
        
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        log_error("run_helm_command", e)
        return False, str(e)

def load_charts_cache_from_disk() -> Tuple[List[str], Optional[datetime]]:
    """Load charts cache from disk."""
    try:
        if not _charts_cache_file.exists():
            log_debug("load_charts_cache_from_disk", "No cache file found")
            return [], None
        
        cache_data = json.loads(_charts_cache_file.read_text())
        charts = cache_data.get("charts", [])
        timestamp_str = cache_data.get("timestamp")
        
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str)
            log_debug("load_charts_cache_from_disk", f"Loaded {len(charts)} charts from disk cache (timestamp: {timestamp})")
            return charts, timestamp
        else:
            log_debug("load_charts_cache_from_disk", f"Loaded {len(charts)} charts from disk cache (no timestamp)")
            return charts, None
            
    except Exception as e:
        log_debug("load_charts_cache_from_disk", f"Failed to load cache from disk: {str(e)}")
        return [], None

def save_charts_cache_to_disk(charts: List[str], timestamp: datetime) -> bool:
    """Save charts cache to disk."""
    try:
        cache_data = {
            "charts": charts,
            "timestamp": timestamp.isoformat(),
            "version": "1.0"
        }
        _charts_cache_file.write_text(json.dumps(cache_data, indent=2))
        log_debug("save_charts_cache_to_disk", f"Saved {len(charts)} charts to disk cache")
        return True
    except Exception as e:
        log_debug("save_charts_cache_to_disk", f"Failed to save cache to disk: {str(e)}")
        return False

def get_eea_charts(force_refresh: bool = False, allow_repo_fetch: bool = True) -> List[str]:
    """Get EEA charts list with persistent caching mechanism."""
    global _cached_charts, _charts_cache_timestamp
    
    try:
        now = datetime.now()
        
        # Load from disk cache if memory cache is empty
        if not _cached_charts:
            disk_charts, disk_timestamp = load_charts_cache_from_disk()
            if disk_charts:
                _cached_charts = disk_charts
                _charts_cache_timestamp = disk_timestamp
                log_debug("get_eea_charts", f"Loaded {len(disk_charts)} charts from disk cache")
        
        # Check if we have cached data and it's still valid
        if (not force_refresh and _cached_charts and _charts_cache_timestamp and 
            (now - _charts_cache_timestamp).total_seconds() < _charts_cache_duration):
            log_debug("get_eea_charts", f"Using cached charts list with {len(_cached_charts)} items")
            return _cached_charts
        
        # Only fetch from repository if explicitly allowed (for browse charts screen)
        if not allow_repo_fetch:
            log_debug("get_eea_charts", "Repository fetch not allowed, using existing cache or fallback")
            return _cached_charts if _cached_charts else EEA_CHARTS
        
        # Fetch fresh data from repo
        log_debug("get_eea_charts", "Fetching fresh charts list from repository")
        fresh_charts = fetch_charts_from_helm_repo()
        
        if fresh_charts:
            # Update memory cache
            _cached_charts = fresh_charts
            _charts_cache_timestamp = now
            
            # Save to disk cache
            save_charts_cache_to_disk(fresh_charts, now)
            
            log_debug("get_eea_charts", f"Updated cache with {len(fresh_charts)} charts")
            return fresh_charts
        else:
            # If fetch failed, return cached data if available, otherwise fallback to static list
            if _cached_charts:
                log_debug("get_eea_charts", "Fetch failed, using cached charts")
                return _cached_charts
            else:
                log_debug("get_eea_charts", "Fetch failed and no cache, using static fallback")
                return EEA_CHARTS  # Fallback to static list from models
        
    except Exception as e:
        log_error("get_eea_charts", e)
        # Return cached data or static fallback
        return _cached_charts if _cached_charts else EEA_CHARTS

def categorize_chart(chart_name: str) -> str:
    """Categorize EEA chart by type."""
    frontend_charts = ['advisory-board-frontend', 'eea-website-frontend', 'fise-frontend', 
                       'lcp-frontend', 'mars-frontend', 'wise-frontend', 'volto']
    backend_charts = ['advisory-board-backend', 'eea-website-backend', 'fise-backend',
                      'mars-backend', 'wise-backend', 'datadict', 'contreg']
    infrastructure_charts = ['postgres', 'redis', 'memcached', 'elastic6', 'elastic7',
                            'opensearch', 'opensearch-dashboards', 'haproxy', 'varnish']
    
    if chart_name in frontend_charts:
        return "Frontend"
    elif chart_name in backend_charts:
        return "Backend" 
    elif chart_name in infrastructure_charts:
        return "Infrastructure"
    else:
        return "Other"

def filter_charts(search_term: str, charts: List[str] = None) -> List[str]:
    """Filter charts by search term."""
    if charts is None:
        charts = get_eea_charts(allow_repo_fetch=False)  # Fast mode - use cache only
    
    if not search_term:
        return charts
    
    search_lower = search_term.lower()
    return [chart for chart in charts if search_lower in chart.lower()]

def get_chart_suggestions(partial_name: str) -> List[str]:
    """Get chart name suggestions based on partial input."""
    eea_charts = get_eea_charts(allow_repo_fetch=False)  # Fast mode - use cache only
    
    if not partial_name:
        return eea_charts[:10]  # Return first 10 as default
    
    partial_lower = partial_name.lower()
    suggestions = []
    
    # Exact matches first
    for chart in eea_charts:
        if chart.lower().startswith(partial_lower):
            suggestions.append(chart)
    
    # Partial matches
    for chart in eea_charts:
        if partial_lower in chart.lower() and chart not in suggestions:
            suggestions.append(chart)
    
    return suggestions[:10]  # Limit to 10 suggestions

def create_chart_table_data(charts: List[str] = None) -> List[Tuple[str, str, str]]:
    """Create table data for chart display."""
    if charts is None:
        charts = get_eea_charts(allow_repo_fetch=False)  # Fast mode - use cache only
    
    table_data = []
    for chart in charts:
        category = categorize_chart(chart)
        description = f"EEA {category} application"
        table_data.append((chart, category, description))
    return table_data

# ==============================================================================
# CONFIGURATION FUNCTIONS 
# ==============================================================================

def generate_configmap_yaml(fleet_config: FleetConfig) -> str:
    """Generate ConfigMap YAML content with ONLY values.yaml in data."""
    try:
        values_yaml = generate_values_yaml(fleet_config)

        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{fleet_config.app_name}-config",
                "namespace": fleet_config.namespace,
            },
            "data": {
                "values.yaml": values_yaml or ""
            },
        }

        return yaml.dump(configmap, default_flow_style=False)
    except Exception as e:
        log_error("generate_configmap_yaml", e, {"fleet_config": fleet_config.app_name})
        return ""

def generate_fleet_yaml(fleet_config: FleetConfig) -> str:
    """Generate fleet.yaml content with enhanced chart metadata from helm secrets."""
    try:
        fleet_yaml_config = fleet_config.fleet_yaml_config
        
        # Build helm section with basic configuration
        helm_config = {
            "chart": fleet_config.chart_name,
            "repo": fleet_config.helm_repo,
            "version": fleet_config.chart_version or "latest",
            # Reference values from ConfigMap instead of embedding
            "valuesFrom": [
                {
                    "configMapKeyRef": {
                        "name": f"{fleet_config.app_name}-config",
                        "key": "values.yaml",
                    }
                }
            ],
        }
        
        # Add chart metadata if available (from helm secret extraction)
        chart_metadata = {}
        if hasattr(fleet_config, 'chart_metadata') and fleet_config.chart_metadata:
            chart_metadata = fleet_config.chart_metadata
        elif fleet_config.is_existing_release and fleet_config.release_name:
            # Try to get chart metadata from the release secret for existing releases
            try:
                kubeconfig_path = get_current_kubeconfig()
                if not kubeconfig_path:
                    kubeconfig_path = generate_temp_kubeconfig()
                    if kubeconfig_path:
                        set_current_kubeconfig(kubeconfig_path)
                
                if kubeconfig_path:
                    secret_metadata = get_helm_release_secret_metadata(
                        fleet_config.release_name, 
                        fleet_config.namespace, 
                        kubeconfig_path
                    )
                    if secret_metadata:
                        chart_metadata = secret_metadata
                        log_debug("generate_fleet_yaml", f"Retrieved chart metadata for {fleet_config.release_name}: {chart_metadata}")
            except Exception as e:
                log_debug("generate_fleet_yaml", f"Could not get chart metadata for {fleet_config.release_name}: {str(e)}")
        
        # Add metadata as comments in the YAML if available
        metadata_comments = []
        if chart_metadata:
            if chart_metadata.get("name"):
                metadata_comments.append(f"# Chart Name: {chart_metadata['name']}")
            if chart_metadata.get("version"):
                metadata_comments.append(f"# Chart Version: {chart_metadata['version']}")
                # Also update the version in helm config if not already set
                if not fleet_config.chart_version or fleet_config.chart_version == "latest":
                    helm_config["version"] = chart_metadata["version"]
            if chart_metadata.get("appVersion"):
                metadata_comments.append(f"# App Version: {chart_metadata['appVersion']}")
            if chart_metadata.get("description"):
                metadata_comments.append(f"# Description: {chart_metadata['description']}")
        
        fleet_content = {
            "defaultNamespace": fleet_config.namespace,
            "helm": helm_config,
        }
        
        # Add cluster targeting if specified
        if fleet_config.target_cluster:
            fleet_content["targets"] = [{
                "name": fleet_config.target_cluster,
                "clusterSelector": {
                    "matchLabels": {
                        "management.cattle.io/cluster-name": fleet_config.target_cluster
                    }
                }
            }]
        
        # Add rollout strategy
        fleet_content["rolloutStrategy"] = fleet_yaml_config.rollout_strategy
        
        # Generate YAML and prepend metadata comments
        fleet_yaml = yaml.dump(fleet_content, default_flow_style=False)
        
        if metadata_comments:
            comments_section = "\n".join(metadata_comments) + "\n---\n"
            fleet_yaml = comments_section + fleet_yaml
        
        return fleet_yaml
    except Exception as e:
        log_error("generate_fleet_yaml", e, {"fleet_config": fleet_config.app_name})
        return ""

def generate_values_yaml(fleet_config: FleetConfig) -> str:
    """Generate values.yaml content."""
    try:
        if fleet_config.values:
            return yaml.dump(fleet_config.values, default_flow_style=False)
        else:
            return DEFAULT_VALUES_TEMPLATE.format(chart_name=fleet_config.chart_name)
    except Exception as e:
        log_error("generate_values_yaml", e, {"fleet_config": fleet_config.app_name})
        return ""

def load_fleet_configuration(config_path: str) -> Optional[FleetConfig]:
    """Load Fleet configuration from file."""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            return None
        
        data = yaml.safe_load(config_file.read_text())
        if not data:
            return None
        
        # Convert dict to FleetConfig (simplified)
        return FleetConfig(
            app_name=data.get("app_name", ""),
            namespace=data.get("namespace", ""),
            chart_name=data.get("chart_name", ""),
            chart_version=data.get("chart_version", ""),
            helm_repo=data.get("helm_repo", EEA_HELM_REPO),
            values=data.get("values", {}),
            target_cluster=data.get("target_cluster", ""),
            dependencies=data.get("dependencies", [])
        )
    except Exception as e:
        log_error("load_fleet_configuration", e, {"config_path": config_path})
        return None

def get_default_helm_values(chart_name: str) -> Dict[str, Any]:
    """Get default Helm values template for chart."""
    return {
        "replicaCount": 1,
        "image": {
            "repository": f"eeacms/{chart_name}",
            "pullPolicy": "IfNotPresent",
            "tag": "latest"
        },
        "service": {
            "type": "ClusterIP",
            "port": 80
        },
        "ingress": {
            "enabled": False
        },
        "resources": {
            "limits": {
                "cpu": "500m",
                "memory": "512Mi"
            },
            "requests": {
                "cpu": "250m", 
                "memory": "128Mi"
            }
        }
    }

# ==============================================================================
# DEPLOYMENT FUNCTIONS
# ==============================================================================

def deploy_configmap(fleet_config: FleetConfig) -> Tuple[bool, str]:
    """Deploy ConfigMap to cluster."""
    try:
        # Validate namespace exists (should exist in Rancher beforehand)
        if not namespace_exists(fleet_config.namespace):
            return False, f"Namespace '{fleet_config.namespace}' does not exist in current Rancher context. Please create it first."
        
        # Generate ConfigMap YAML
        configmap_content = generate_configmap_yaml(fleet_config)
        if not configmap_content:
            return False, "Failed to generate ConfigMap content"
        
        # Write to temporary file and apply
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(configmap_content)
            temp_file = f.name
        
        try:
            success, output = run_rancher_command(["kubectl", "apply", "-f", temp_file])
            if success:
                return True, f"ConfigMap {fleet_config.app_name}-config deployed successfully"
            else:
                return False, f"Failed to deploy ConfigMap: {output}"
        finally:
            Path(temp_file).unlink(missing_ok=True)
            
    except Exception as e:
        log_error("deploy_configmap", e, {"fleet_config": fleet_config.app_name})
        return False, str(e)

def deploy_multiple_configmaps(fleet_configs: List[FleetConfig]) -> Dict[str, Tuple[bool, str]]:
    """Deploy multiple ConfigMaps."""
    results = {}
    for config in fleet_configs:
        success, message = deploy_configmap(config)
        results[config.app_name] = (success, message)
    return results

def check_cluster_connectivity() -> Tuple[bool, str]:
    """Check if cluster is accessible via Rancher."""
    try:
        # Check if we can list namespaces (basic connectivity test)
        success, output = run_rancher_command(["namespaces", "ls", "--format", "json"])
        if success:
            return True, "Cluster accessible via Rancher"
        else:
            return False, f"Cluster not accessible: {output}"
    except Exception as e:
        log_error("check_cluster_connectivity", e)
        return False, str(e)

# ==============================================================================
# FILE SYSTEM FUNCTIONS
# ==============================================================================

def read_file(file_path: str) -> Optional[str]:
    """Read file contents safely."""
    try:
        return Path(file_path).read_text(encoding='utf-8')
    except Exception as e:
        log_error("read_file", e, {"file_path": file_path})
        return None

def write_file(file_path: str, content: str) -> bool:
    """Write file contents safely."""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        log_error("write_file", e, {"file_path": file_path})
        return False

def create_temp_file(content: str, suffix: str = '.tmp') -> Optional[str]:
    """Create temporary file with content."""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name
    except Exception as e:
        log_error("create_temp_file", e)
        return None

def list_directory(directory: str) -> List[str]:
    """List directory contents."""
    try:
        path = Path(directory)
        if path.is_dir():
            return [item.name for item in path.iterdir()]
        return []
    except Exception as e:
        log_error("list_directory", e, {"directory": directory})
        return []

def validate_directory_path(path: str) -> bool:
    """Validate that path is a valid directory."""
    try:
        return Path(path).is_dir()
    except Exception:
        return False

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def result_ok(data: Any = None) -> Dict[str, Any]:
    """Standard success response format."""
    return {"success": True, "data": data, "error": None}

def result_error(error: str, data: Any = None) -> Dict[str, Any]:
    """Standard error response format."""
    return {"success": False, "data": data, "error": error}

def require_keys(data: Dict, keys: List[str]) -> bool:
    """Validate that required keys are present in data."""
    return all(key in data for key in keys)

# ==============================================================================
# ADVANCED DIAGNOSTIC FUNCTIONS
# ==============================================================================

def debug_rancher_config() -> Dict[str, Any]:
    """Debug current Rancher configuration and connectivity."""
    try:
        debug_info = {
            "rancher_version": None,
            "current_context": None,
            "available_projects": None,
            "cluster_connectivity": None,
            "kubeconfig_status": None,
            "namespace_access": None
        }
        
        # Check Rancher version
        success, output = run_rancher_command(["--version"])
        debug_info["rancher_version"] = output if success else f"Error: {output}"
        
        # Check current context
        success, output = run_rancher_command(["context", "current"])
        debug_info["current_context"] = output if success else f"Error: {output}"
        
        # List available projects
        projects = get_rancher_projects()
        debug_info["available_projects"] = f"Found {len(projects)} projects"
        
        # Test cluster connectivity
        success, message = check_cluster_connectivity()
        debug_info["cluster_connectivity"] = message
        
        # Test kubeconfig generation
        kubeconfig_path = generate_temp_kubeconfig()
        if kubeconfig_path:
            debug_info["kubeconfig_status"] = f"Generated: {kubeconfig_path}"
            cleanup_temp_kubeconfig(kubeconfig_path)
        else:
            debug_info["kubeconfig_status"] = "Failed to generate kubeconfig"
        
        # Test namespace access
        namespaces = list_namespaces()
        debug_info["namespace_access"] = f"Can access {len(namespaces)} namespaces"
        
        return debug_info
        
    except Exception as e:
        log_error("debug_rancher_config", e)
        return {"error": str(e)}

def test_kubeconfig_generation() -> Tuple[bool, str]:
    """Test kubeconfig generation and validation."""
    try:
        # Generate temporary kubeconfig
        kubeconfig_path = generate_temp_kubeconfig()
        if not kubeconfig_path:
            return False, "Failed to generate kubeconfig"
        
        try:
            # Test if kubeconfig is valid by reading it
            kubeconfig_content = read_file(kubeconfig_path)
            if not kubeconfig_content:
                return False, "Generated kubeconfig is empty"
            
            # Check if it contains expected kubernetes config structure
            import yaml
            try:
                config_data = yaml.safe_load(kubeconfig_content)
                if not isinstance(config_data, dict) or "apiVersion" not in config_data:
                    return False, "Generated kubeconfig is not valid YAML"
                
                return True, f"Kubeconfig generated successfully: {len(kubeconfig_content)} bytes"
                
            except yaml.YAMLError as e:
                return False, f"Generated kubeconfig is not valid YAML: {e}"
            
        finally:
            # Clean up temporary kubeconfig
            cleanup_temp_kubeconfig(kubeconfig_path)
            
    except Exception as e:
        log_error("test_kubeconfig_generation", e)
        return False, str(e)

def validate_namespace_access_detailed() -> Dict[str, Any]:
    """Detailed validation of namespace access and permissions."""
    try:
        result = {
            "accessible_namespaces": [],
            "total_count": 0,
            "rancher_context": None,
            "errors": []
        }
        
        # Get current rancher context
        context, cluster_id, cluster_name = get_current_rancher_context()
        result["rancher_context"] = {
            "context": context,
            "cluster_id": cluster_id, 
            "cluster_name": cluster_name
        }
        
        # List accessible namespaces
        namespaces = list_namespaces()
        result["accessible_namespaces"] = namespaces
        result["total_count"] = len(namespaces)
        
        # Test access to each namespace
        for namespace in namespaces[:5]:  # Test first 5 to avoid too many calls
            can_access, message = validate_namespace_access(namespace)
            if not can_access:
                result["errors"].append(f"Cannot access {namespace}: {message}")
        
        return result
        
    except Exception as e:
        log_error("validate_namespace_access_detailed", e)
        return {"error": str(e)}

def cleanup_on_exit():
    """Clean up resources on application exit."""
    if _current_kubeconfig_path:
        cleanup_temp_kubeconfig(_current_kubeconfig_path)
        log_debug("cleanup_on_exit", "Cleaned up kubeconfig on application exit")

atexit.register(cleanup_on_exit)

# Initialize on module load
load_settings()
initialize_directories()
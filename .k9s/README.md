# Example K9s configuration file

```yaml
# $XDG_CONFIG_HOME/k9s/config.yml
#
# K9s keeps its configuration inside of the `k9s` directory. The location of
# this directory is OS-specific. K9s leverages XDG (see link below) to
# determine this location. The command `k9s info` can be used to show the
# location of the configuration file.
#
# Alternatively, you can set the `K9SCONFIG` environment variable in order to
# specify the location K9s should look for its configuration.
#
# Default OS-specific locations:
#   * Linux: ~/.config/k9s
#   * macOS: ~/Library/Application Support/k9s
#   * Windows: %LOCALAPPDATA%\k9s
#
# XDG Base Directory Specification:
#   * https://github.com/adrg/xdg/blob/master/README.md

k9s:
  # UI poll interval (seconds). Default 2
  refreshRate: 2
  # Number of retries once the connection to the api-server is lost. Default 15
  maxConnRetry: 5
  # Whether to enable mouse support. Default false
  enableMouse: true
  # Whether to hide the K9s header. Default false
  headless: false
  # Whether to hide the K9s logo. Default false
  logoless: false
  # Whether to hide K9s crumbs. Default false
  crumbsless: false
  # Whether cluster modification commands (delete/kill/edit) are disabled.
  # Default false
  readOnly: false
  # Whether icons are displayed (not all terminals support these characters).
  # Default false
  noIcons: false
  # Log configuration
  logger:
    # Number of log lines to display. Default 100
    tail: 100
    # Number of log lines to allow in the view. Default 5000
    buffer: 5000
    # Duration (seconds) to go back in the log timeline. Setting this value to
    # -1 will show all available logs. Default 300 (5 minutes)
    sinceSeconds: 300
    # Whether to use the full screen when displaying logs. Default false
    fullScreenLogs: false
    # Whether to wrap log lines. Default false
    textWrap: false
    # Whether to show timestamp info in log lines. Default false
    showTime: false
  # The current Kubernetes context. Defaults to the current context
  currentContext: minikube
  # The current Kubernetes cluster. Defaults to the current context cluster
  currentCluster: minikube
  # Persist cluster-specific preferences
  clusters:
    minikube:
      namespace:
        active: all
        favorites:
        - all
        - default
      view:
        active: pod
      featureGates:
        # Whether to enable NodeShell support. This allows K9s to shell into
        # Nodes if needed. Default false
        #
        # See: https://k9scli.io/topics/shell
        nodeShell: false
      # Shell Pod configuration (nodeShell must be enabled)
      shellPod:
        # Container image to use when getting a shell to a Node.
        image: busybox:1.31
        # Commands to pass to the container.
        command: []
        # Arguments to pass to the container.
        args: []
        # Namespace to use for the Pod when getting a shell to a Node.
        namespace: default
        # Resource limits for the Pod when getting a shell to a Node.
        limits:
          cpu: 100m
          memory: 100Mi
      # The IP address to use when using `port-forward`.
      #
      # See: https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster
      portForwardAddress: localhost
  thresholds:
    cpu:
      critical: 90
      warn: 70
    memory:
      critical: 90
      warn: 70
  # Location of screen dump. Use `k9s info` to show location.
  # Default: '%temp_dir%/k9s-screens-%username%'
  screenDumpDir: /var/folders/h3/7qbwch0j3db67hk9pgqtcd580000gq/T/k9s-screens-nickolaskraus
```

#!/usr/bin/env bash
set -euo pipefail

IMAGE="${JENKINS_AGENT_IMAGE:-book-my-date/jenkins-agent:1.0.0}"
WORKSPACE_DIR="${WORKSPACE:-$(pwd)}"

resolve_host_path() {
    local path="$1"
    local best_mount=""
    local best_root=""
    local _ _ _ root mount_point _
    if [ -z "$path" ] || [ ! -r /proc/self/mountinfo ]; then
        printf '%s\n' "$path"
        return
    fi
    while read -r _ _ _ root mount_point _; do
        case "$path" in
            "$mount_point"|"$mount_point"/*)
                if [ "${#mount_point}" -gt "${#best_mount}" ]; then
                    best_mount="$mount_point"
                    best_root="$root"
                fi
                ;;
        esac
    done < /proc/self/mountinfo
    if [ -n "$best_mount" ]; then
        printf '%s%s\n' "$best_root" "${path#"$best_mount"}"
    else
        printf '%s\n' "$path"
    fi
}

HOST_WORKSPACE_DIR="${HOST_WORKSPACE_DIR:-$(resolve_host_path "$WORKSPACE_DIR")}"
if [ ! -d "$WORKSPACE_DIR" ]; then
    echo "ERROR: Jenkins workspace directory not found: $WORKSPACE_DIR" >&2
    exit 1
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "ERROR: Docker image $IMAGE is missing. Run the Prepare Agent stage first."
    exit 1
fi

env_names=(
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_SESSION_TOKEN
    AWS_DEFAULT_REGION
    S3_BUCKET
    BUILD_NUMBER
    GIT_COMMIT
    GIT_BRANCH
    TAG_NAME
    VENV_DIR
    SONAR_SETTINGS
    SONAR_HOST_URL
    SONAR_PROJECT_KEY
    SONAR_GATE_TIMEOUT
    SONAR_AUTH_TOKEN
    SONAR_TOKEN
    QT_QPA_PLATFORM
)

docker_args=(
    run
    --rm
    --interactive
    --user "$(id -u):$(id -g)"
    --volume "${HOST_WORKSPACE_DIR}:/workspace"
    --workdir /workspace
    --env HOME=/tmp
)

for name in "${env_names[@]}"; do
    if [ -n "${!name:-}" ]; then
        docker_args+=(--env "$name")
    fi
done

if [ "$#" -gt 0 ]; then
    exec docker "${docker_args[@]}" "$IMAGE" bash -lc "$*"
fi
exec docker "${docker_args[@]}" "$IMAGE" bash -s

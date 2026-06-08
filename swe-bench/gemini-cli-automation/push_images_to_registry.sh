#!/bin/bash
# Push all gemini-eval overlay images to GitHub Container Registry
# This preserves the exact digests for reproducibility

set -e

REGISTRY="ghcr.io"
USER="nashid"
REPO_PREFIX="gemini-eval"

echo "=== Pushing Gemini-eval overlay images to $REGISTRY/$USER/$REPO_PREFIX ==="
echo ""
echo "Prerequisites:"
echo "1. Docker daemon running"
echo "2. GitHub token with write:packages scope"
echo "3. Logged in: echo \$GITHUB_TOKEN | docker login ghcr.io -u $USER --password-stdin"
echo ""
read -p "Press Enter to continue..."

# Get list of all gemini-eval images
images=$(docker images "gemini-eval/*" --format "{{.Repository}}:{{.Tag}}" | sort)

if [ -z "$images" ]; then
    echo "ERROR: No gemini-eval images found in local Docker cache"
    echo "Have you built the overlay images?"
    exit 1
fi

total=$(echo "$images" | wc -l | tr -d ' ')
echo "Found $total images to push"
echo ""

count=0
failed=()

for img in $images; do
    count=$((count + 1))

    # Extract image name without prefix
    img_name=$(echo "$img" | sed 's/gemini-eval\///')
    img_name_clean=$(echo "$img_name" | sed 's/:latest//')

    # Construct registry URL
    registry_img="${REGISTRY}/${USER}/${REPO_PREFIX}/${img_name}"

    echo "[$count/$total] Processing: $img_name_clean"
    echo "  Local:    $img"
    echo "  Registry: $registry_img"

    # Tag for registry
    if docker tag "$img" "$registry_img"; then
        echo "  ✓ Tagged"
    else
        echo "  ✗ Tagging failed"
        failed+=("$img")
        continue
    fi

    # Push to registry
    echo "  Pushing..."
    if docker push "$registry_img" > /tmp/docker-push-$$.log 2>&1; then
        # Extract digest from push output
        digest=$(docker image inspect "$registry_img" --format '{{index .RepoDigests 0}}' 2>/dev/null || echo "unknown")
        echo "  ✓ Pushed: $digest"
    else
        echo "  ✗ Push failed (see /tmp/docker-push-$$.log)"
        cat /tmp/docker-push-$$.log
        failed+=("$img")
    fi

    echo ""
done

echo "=== Summary ==="
echo "Total images: $total"
echo "Successfully pushed: $((total - ${#failed[@]}))"
echo "Failed: ${#failed[@]}"

if [ ${#failed[@]} -gt 0 ]; then
    echo ""
    echo "Failed images:"
    for f in "${failed[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

echo ""
echo "✓ All images successfully pushed to $REGISTRY/$USER/$REPO_PREFIX"
echo ""
echo "Next steps:"
echo "1. Update image_manifest.json to reference registry URLs"
echo "2. Make repository packages public on GitHub (if needed)"
echo "3. Document in TOSEM paper"

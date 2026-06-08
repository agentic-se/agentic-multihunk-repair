# Docker Hub Image Sync

Scripts for pushing/pulling qwen-eval Docker images to/from Docker Hub.

## Push Images to Docker Hub

Push all 32 qwen-eval images to `noornashid/maple` repository:

```bash
# 1. Login to Docker Hub (one-time)
docker login

# 2. Push all images
./push_images_to_dockerhub.sh
```

**What this does:**
- Tags all `qwen-eval/*:latest` images as `noornashid/maple:qwen-eval-*`
- Pushes them to Docker Hub
- Shows progress for all 32 images
- Reports success/failure summary

**Expected output:**
```
[1/32] Processing: astropy_1776_astropy-13033
  Source: qwen-eval/astropy_1776_astropy-13033:latest
  Target: noornashid/maple:qwen-eval-astropy_1776_astropy-13033
  ✓ Tagged successfully
  Pushing to Docker Hub...
  ✓ Pushed successfully
...
```

**Note:** This will upload **~100 GB** total (32 images × ~3 GB each). Make sure you have:
- Good internet connection
- Docker Hub storage quota (free tier has unlimited public repositories)
- Time (~30-60 minutes depending on upload speed)

## Pull Images from Docker Hub

Pull all 32 qwen-eval images from Docker Hub:

```bash
./pull_images_from_dockerhub.sh
```

**What this does:**
- Pulls all images from `noornashid/maple:qwen-eval-*`
- Retags them as local `qwen-eval/*:latest` format
- Makes them ready for use with `automated_qwen_code.py`

**Use case:** 
- Setting up on a new machine
- Sharing with collaborators
- Avoiding the ~2-hour build process

## Benefits of Using Docker Hub

1. **Reproducibility**: Others can use exact same images
2. **No Rebuild**: Skip the 2-hour image build process
3. **Collaboration**: Share with team members
4. **RepoDigests**: Images will have proper digests (fixes `overlay_digest: null`)

## Image Naming Convention

**Local format:**
```
qwen-eval/astropy_1776_astropy-13033:latest
```

**Docker Hub format:**
```
noornashid/maple:qwen-eval-astropy_1776_astropy-13033
```

## View on Docker Hub

After pushing, view your images at:
https://hub.docker.com/r/noornashid/maple/tags

## Disk Space

**Local images:** ~100 GB (32 images)  
**Docker Hub:** Free unlimited storage for public images

## Troubleshooting

**Problem:** "unauthorized: authentication required"  
**Solution:** Run `docker login` first

**Problem:** "denied: requested access to the resource is denied"  
**Solution:** Make sure you own the `noornashid/maple` repository

**Problem:** Images too large / slow upload  
**Solution:** 
- Use faster internet connection
- Push in batches (comment out some instances in the script)
- Consider using Docker Hub's layer caching

## Advanced: Push/Pull Specific Images

Edit the scripts to only process certain images:

```bash
# In push_images_to_dockerhub.sh, add filter:
IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^qwen-eval/astropy" | sort)

# Or manually push one:
docker tag qwen-eval/astropy_1776_astropy-13033:latest noornashid/maple:qwen-eval-astropy_1776_astropy-13033
docker push noornashid/maple:qwen-eval-astropy_1776_astropy-13033
```

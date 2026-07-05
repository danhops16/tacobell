# Taco Bell Tracker

A GitHub Pages site to track every Taco Bell location you've visited.

## Features

- **7,300+ locations** across the United States, Canada, and the United Kingdom
- Interactive map with clustering
- Search by city, state, or address
- Filter by country or visited status
- Mark locations as visited (saved in your browser via localStorage)
- Export / import your visited list as JSON
- "Near me" to find the closest Taco Bell

## Live site

After pushing to GitHub and enabling Pages, your site will be at:

**https://danhops16.github.io/tacobell/**

## Setup

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial Taco Bell tracker site"
git branch -M main
git remote add origin https://github.com/danhops16/tacobell.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo **Settings → Pages**
2. Under **Build and deployment**, set Source to **Deploy from a branch**
3. Select branch **main** and folder **/ (root)**
4. Click **Save**

The site will be live in a minute or two.

## Updating location data

Location data comes from public sources and is bundled in `data/locations.json`. To refresh:

```bash
python3 scripts/build_locations.py
```

Data sources:
- **US** (~7,100): [stiles/locations](https://github.com/stiles/locations) (MIT)
- **Canada** (~156): [tacobell.ca](https://www.tacobell.ca/en/store-locator) store locator
- **UK** (~37): Community-maintained [gist](https://gist.github.com/SteGriff/00ed26790b028c06200d56041e6ba23f)

## Visited data

Your visited locations are stored in **localStorage** in your browser. They are not synced to GitHub. Use **Export** to back up your list, and **Import** to restore it on another device.

## License

Location data from third-party sources retains their respective licenses. Site code is MIT.

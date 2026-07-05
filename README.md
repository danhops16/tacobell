# Taco Bell Tracker

A GitHub Pages site to track every Taco Bell location you've visited.

## Features

- **8,900+ locations** across 9 countries (US, Canada, UK, Spain, India, Australia, Finland, Netherlands, Philippines)
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

Location data comes from [All The Places](https://alltheplaces.xyz/) (CC0), updated weekly. The build script downloads official store data for:

- **United States** (~8,200)
- **Canada** (~200)
- **United Kingdom** (~160)
- **Spain** (~180)
- **India** (~110)
- **Australia**, **Finland**, **Netherlands**, **Philippines**

Taco Bell operates in 35+ countries total; this covers every country with a public store-locator API in the All The Places project. More countries can be added as spiders become available.

## Visited data

Your visited locations are stored in **localStorage** in your browser. They are not synced to GitHub. Use **Export** to back up your list, and **Import** to restore it on another device.

## License

Location data from third-party sources retains their respective licenses. Site code is MIT.

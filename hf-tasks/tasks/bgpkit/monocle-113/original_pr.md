# bgpkit/monocle-113 (original PR)

bgpkit/monocle (#113): refactor: conform config data and cache dirs to xdg spec

closes https://github.com/bgpkit/monocle/issues/111

aside from config and data dirs, i also found out there were hard coded paths for cache (dont seem to be used a lot), so i moved that one to `$XDG_CACHE_HOME/monocle` and fall back to `~/.cache/monocle`

otherwise please see changes indicated in change log

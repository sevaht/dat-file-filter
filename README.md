# dat-file-filter

A command-line tool for making sense of — and slimming down — the `.dat` files
published by cataloguing projects like No-Intro and Redump.

Those dat files list every known dump of every game for a system: all the
regional and language releases, revisions, demos, betas, prototypes, and
multi-disc sets. `dat-file-filter` reads the name of each entry, works out what
each bracketed tag means (region, language, edition, revision, disc, …), groups
together the releases that are really the *same game*, and lets you inspect that
structure or write out a trimmed dat containing just the versions you want.

The tool prefers English: when several regional versions of the same thing
exist, it can pick the best English one (USA first, then other English
releases), and it tells you where no English version exists at all.

## Install

The tool uses [uv](https://docs.astral.sh/uv/). Run it from a clone:

```console
$ uv run dat-file-filter --help
```

Or install it onto your `PATH`:

```console
$ uv tool install .      # or: pipx install .
$ dat-file-filter --help
```

## How it works

There is **one command**. You give it selection flags (what to keep) and output
flags (what to emit); it applies the selection and produces the output(s) you
asked for.

- **Game** — all the entries the tool considers the same game, grouped together.
  Entries are grouped by their title, by the `id`/`cloneofid` clone attributes
  when a dat provides them, and by bundled **clone lists** for releases that
  share neither (e.g. `Biohazard` (JP) and `Resident Evil` (US), or `40 Winks`
  and its German rename `Ruff & Tumble`). See "Grouping across regional names".
- **Variant** — a meaningfully different release: a different edition, revision,
  disc, or an unrecognized tag. Plain regional/language differences are *not*
  separate variants; they're localizations of one variant, and English
  selection chooses between them.

Trees and lists mark every entry:

- `+` **green** — kept, has English.
- `~` **yellow** — kept, but no English version exists (e.g. a Japan-only game
  kept as its own original).
- `-` **red** — removed by the selection.

## Grouping across regional names

Games are often released under different names per region, and most dat files
(all Redump disc dats, for instance) carry no clone ids to link them. The tool
ships with **clone lists** — per-system, hand-curated groupings covering ~100
systems. The practical payoff: with `--best-english`, the Japanese-named
release of a game that also has an English release is dropped in favor of the
English one, while a genuine region exclusive (in no group, no English) is
still kept.

The right clone list is chosen from the dat's system name. **A matching clone
list is required** — if none is found the tool errors rather than silently
grouping without one (clone-list groupings are system-specific and can't be
merged across systems, so this is deliberate). To resolve it:

- `--list-clone-lists` — print the available systems and exit.
- `--system NAME` — use a specific system's clone list (a value from
  `--list-clone-lists`) when the dat's name isn't detected automatically.
- `--no-clone-lists` — proceed without one (group by title/clone id only).
- `--clone-list FILE` — use a specific clone-list JSON file.
- `--clone-list-dir DIR` — detect within a directory (e.g. a fresh checkout of
  the upstream repo) instead of the bundled snapshot.

Refresh the bundled snapshot with `python scripts/update_clonelists.py`.

## Selecting what to keep

With no selection flags, everything is kept. Combine these to narrow it:

- `--releases-only` — drop demos, prototypes/betas, early builds, and non-game
  categories (preproduction, educational, audio, video).
- `--has-english` — drop entries that have no English version.
- `-b` / `--best-english` — keep one version per variant: the best English, or
  the original as a fallback (with `--has-english`, drop it instead of falling
  back).

## Outputs

Pick any (they can combine). With none given, the default is `--tree`.

- `-t` / `--tree` — the grouped variant tree, marked. This is the view to scan
  to check how the tool groups and interprets things, and to preview what a
  selection keeps vs. drops, in context.
- `-l` / `--list` — a flat, one-line-per-entry marked list. Greppable
  (`| grep '^- '` for removed) and good for scripting.
- `-o` / `--output FILE` [`--name NAME`] — write the kept entries to a new dat.
- `--tags` — list tags the parser didn't recognize (candidates to add support
  for).
- `--editions`, `--categories` — survey what's present.

`--tree` and `--list` print a `kept, removed` summary to stderr. Surveys
(`--tags`/`--editions`/`--categories`) reflect the content filters
(`--releases-only`, `--has-english`) but not the `--best-english` reduction, so
tag-hunting still sees the whole set.

## Examples

Look at how a system's games are grouped:

```console
$ dat-file-filter "Nintendo - SNES.dat" | less -R
```

Preview a filter before writing it — see exactly which version of each game is
kept and which are dropped:

```console
$ dat-file-filter --releases-only --best-english --tree "Nintendo - SNES.dat" | less -R
$ dat-file-filter --releases-only --best-english --list "Nintendo - SNES.dat" | grep '^- '
```

Write a trimmed dat — the best English version of each game, keeping the
original where no English exists:

```console
$ dat-file-filter --releases-only --best-english -o "SNES (Best English).dat" "Nintendo - SNES.dat"
```

Best English only, dropping games that have no English at all:

```console
$ dat-file-filter --releases-only --best-english --has-english -o "SNES (English).dat" "Nintendo - SNES.dat"
```

Find tags the parser should learn:

```console
$ dat-file-filter --tags "Nintendo - SNES.dat"
```

## About the written dat

The tool writes a clean, canonical XML form (consistently indented). A written
dat is therefore a *reformatted* copy of the source, not a byte-for-byte one,
but it preserves all entry data (attributes, descriptions, rom lines) and the
DOCTYPE. The header `<name>` changes only if you pass `--name`.

To see exactly what a filter removes, write a **passthrough** copy (no selection
flags) and diff it against the filtered output — both go through the same
serializer, so the only differences are the removed `<game>` blocks:

```console
$ dat-file-filter -o full.dat "Nintendo - SNES.dat"                 # pristine full copy
$ dat-file-filter --best-english -o filtered.dat "Nintendo - SNES.dat"
$ diff full.dat filtered.dat                                        # only removed entries
```

### Clone (`id`/`cloneofid`) links

The output's parent-clone links are made to reflect how the tool groups games:

- An already-valid clone group whose parent is still present is left untouched,
  so a passthrough of a No-Intro/Redump dat keeps its existing links.
- If a filter removes a game's original parent, the surviving entries are
  re-linked (to the **best English** entry as the new parent) instead of being
  left with a `cloneofid` pointing at something no longer present.
- If entries are grouped only by matching titles (most dat files carry no clone
  ids at all), the tool assigns ids and links them — again with the best
  English entry as parent — creating a clone group that didn't exist in the
  source.

## Development

```console
$ uv sync
$ ./checks
```

## Credits

The clone lists under `src/dat_file_filter/clonelists/` are vendored from
[Retool](https://github.com/unexpectedpanda/retool-clonelists-metadata)
(unexpectedpanda), used under the BSD-3-Clause license — see
`src/dat_file_filter/clonelists/LICENSE`. Retool is retired; this project keeps
a working snapshot and can refresh it via `scripts/update_clonelists.py`.

# California legal datasets — common tasks.
#
#   make law        refresh the structured statute snapshot (data/law/*.jsonl.gz)
#   make db         build the queryable statute SQLite database (data/leginfo.sqlite)
#   make bills      import bills from the official bulk archive (needs network)
#   make selfhelp   build the Self-Help Guide snapshot (data/selfhelp/pages.jsonl.gz)
#   make selfhelp-db  build the Self-Help SQLite database (data/selfhelp/selfhelp.sqlite)
#   make verify     sanity-check both datasets
#   make test       run the test suite

PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

.PHONY: help law db selfhelp selfhelp-db selfhelp-live html md bills verify stats test search search-selfhelp clean

help:
	@grep -E '^[a-z-]+:' Makefile | sed 's/^/  make /'

law:
	$(PYTHON) -m leginfo collect-law

db:
	$(PYTHON) -m leginfo build-db

selfhelp:
	$(PYTHON) -m selfhelp collect

selfhelp-db:
	$(PYTHON) -m selfhelp build-db

selfhelp-live:
	$(PYTHON) -m selfhelp collect --live

html:
	$(PYTHON) -m leginfo export-html

md:
	$(PYTHON) -m leginfo export-markdown

bills:
	$(PYTHON) -m leginfo import-bills

verify:
	$(PYTHON) -m leginfo verify
	$(PYTHON) -m selfhelp verify

stats:
	$(PYTHON) -m leginfo stats
	$(PYTHON) -m selfhelp stats

test:
	$(PYTHON) -m pytest -q

search:
	@test -n "$(Q)" || (echo "usage: make search Q=\"public records act\"" && exit 1)
	$(PYTHON) -m leginfo search "$(Q)"

search-selfhelp:
	@test -n "$(Q)" || (echo "usage: make search-selfhelp Q=\"fee waiver\"" && exit 1)
	$(PYTHON) -m selfhelp search "$(Q)"

clean:
	rm -rf data/raw data/leginfo.sqlite* .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

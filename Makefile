# California Legislative Information dataset — common tasks.
#
#   make law      refresh the structured statute snapshot (data/law/*.jsonl.gz)
#   make db       build the queryable SQLite database (data/leginfo.sqlite)
#   make bills    import bills from the official bulk archive (needs network)
#   make verify   sanity-check the dataset
#   make test     run the test suite

PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

.PHONY: help law db html md bills verify test search clean

help:
	@grep -E '^[a-z-]+:' Makefile | sed 's/^/  make /'

law:
	$(PYTHON) -m leginfo collect-law

db:
	$(PYTHON) -m leginfo build-db

html:
	$(PYTHON) -m leginfo export-html

md:
	$(PYTHON) -m leginfo export-markdown

bills:
	$(PYTHON) -m leginfo import-bills

verify:
	$(PYTHON) -m leginfo verify

stats:
	$(PYTHON) -m leginfo stats

test:
	$(PYTHON) -m pytest -q

search:
	@test -n "$(Q)" || (echo "usage: make search Q=\"public records act\"" && exit 1)
	$(PYTHON) -m leginfo search "$(Q)"

clean:
	rm -rf data/raw data/leginfo.sqlite* .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

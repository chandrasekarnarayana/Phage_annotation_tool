.PHONY: help api html clean

SPHINXBUILD ?= sphinx-build
SOURCEDIR = .
BUILDDIR = _build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)"

api:
	@python tools/generate_api_reference.py

html: api
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)"

clean:
	@rm -rf "$(BUILDDIR)" api/generated

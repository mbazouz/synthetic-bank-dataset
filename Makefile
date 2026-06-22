# =============================================================================
# Synthetic bank dataset — Makefile
#
# Simulates a real bank delivering data to a downstream pipeline. Two output
# formats:
#
#   - $(OUTPUT_DIR)/   = raw business format (FR, rich) — for internal use.
#   - $(DELIVERY_DIR)/ = data contract v1 (EN, normalised, S3-mirror
#                        layout). THIS is what the ingest pipeline reads.
#
# Workflow:
#   $ make ship        — tout-en-un : generate + deliver + validate
#   $ make generate    — raw FR output only
#   $ make deliver     — convert raw → contract v1 package (full + deltas)
#   $ make validate    — header check against contract v1
#   $ make minio-up    — local MinIO container
#   $ make minio-seed  — upload delivery to MinIO
#   $ make test        — pytest tests/
#
# COMMON PITFALL: running only `make generate` (or `python -m bank_gen.main`)
# produces the RAW format which the ingest validator REJECTS (French
# column names, missing contract columns). Always chain with `make deliver`,
# or just use `make ship`.
# =============================================================================

PYTHON         ?= .venv/bin/python

# ---------------------------------------------------------------------------
# Variables — override at the command line: make generate CUSTOMERS=2000
# ---------------------------------------------------------------------------

BANK_ID        ?= bank-a
OUTPUT_DIR     ?= ./output
DELIVERY_DIR   ?= ./delivery

# Generation parameters
COUNTRY        ?= us
CUSTOMERS      ?= 500
START          ?= 2023-01-01
END            ?= 2024-06-30
SEED           ?= 4242

# Delivery parameters (full load cutoff + monthly deltas)
CUTOFF         ?= 2024-03-31
DELTAS         ?= 2024-04-30 2024-05-31 2024-06-30

# MinIO local stack parameters
MINIO_ALIAS    ?= synth-local
MINIO_BUCKET   ?= synth-ingestion-local
MINIO_URL      ?= http://localhost:9000
MINIO_ACCESS   ?= minioadmin
MINIO_SECRET   ?= minioadmin
MINIO_IMAGE    ?= minio/minio:RELEASE.2024-11-07T00-52-20Z

# ---------------------------------------------------------------------------
.PHONY: help generate deliver validate ship minio-up minio-seed test clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  COUNTRY=$(COUNTRY)  BANK_ID=$(BANK_ID)  CUSTOMERS=$(CUSTOMERS)  START=$(START)  END=$(END)  SEED=$(SEED)"
	@echo "  CUTOFF=$(CUTOFF)  DELTAS=\"$(DELTAS)\""

# ---------------------------------------------------------------------------
# 1. Generation
# ---------------------------------------------------------------------------
generate: ## Run bank_gen to produce raw output (customers, accounts, transactions)
	$(PYTHON) -m bank_gen.main \
		--country $(COUNTRY) \
		--customers $(CUSTOMERS) \
		--start $(START) \
		--end $(END) \
		--output $(OUTPUT_DIR) \
		--seed $(SEED)

$(OUTPUT_DIR)/customers.csv:
	$(MAKE) generate

# ---------------------------------------------------------------------------
# 2. Delivery
# ---------------------------------------------------------------------------
deliver: $(OUTPUT_DIR)/customers.csv  ## Export contract v1 delivery package (full + deltas)
	$(PYTHON) -m bank_gen.deliver \
		--output $(OUTPUT_DIR) \
		--delivery $(DELIVERY_DIR) \
		--bank-id $(BANK_ID) \
		--cutoff $(CUTOFF) \
		--deltas $(DELTAS)

# ---------------------------------------------------------------------------
# 3. Validation (contract v1 header check — no data leaves the machine)
# ---------------------------------------------------------------------------
validate:  ## Validate CSV headers in the delivery package against contract v1
	$(PYTHON) -m bank_gen._validate_delivery \
		--delivery $(DELIVERY_DIR) \
		--bank-id $(BANK_ID)

# ---------------------------------------------------------------------------
# All-in-one: generate + deliver + validate (recommended for first runs)
# ---------------------------------------------------------------------------
ship: generate deliver validate  ## Generate + deliver + validate in one shot — RECOMMENDED
	@echo ""
	@echo "✅ Dataset ready to ship to the ingest bucket."
	@echo "   Raw business format:  $(OUTPUT_DIR)/"
	@echo "   Contract v1 package:  $(DELIVERY_DIR)/$(BANK_ID)/full/$(CUTOFF)/"
	@echo ""
	@echo "Next step — drop into MinIO (local) or S3 (cloud):"
	@echo "   make minio-seed       # local MinIO"
	@echo "   # or: aws s3 cp --recursive $(DELIVERY_DIR)/$(BANK_ID)/ s3://<bucket>/$(BANK_ID)/"

# ---------------------------------------------------------------------------
# 4. Local MinIO stack
# ---------------------------------------------------------------------------
minio-up:  ## Start local MinIO container (MINIO_URL=$(MINIO_URL))
	docker run -d --name synth-minio \
		-p 9000:9000 -p 9001:9001 \
		-e MINIO_ROOT_USER=$(MINIO_ACCESS) \
		-e MINIO_ROOT_PASSWORD=$(MINIO_SECRET) \
		$(MINIO_IMAGE) \
		server /data --console-address ":9001" \
	|| echo "synth-minio already running"

minio-seed: deliver  ## Upload delivery package to local MinIO bucket
	mc alias set $(MINIO_ALIAS) $(MINIO_URL) $(MINIO_ACCESS) $(MINIO_SECRET) --quiet
	mc mb --ignore-existing $(MINIO_ALIAS)/$(MINIO_BUCKET)
	mc cp --recursive $(DELIVERY_DIR)/$(BANK_ID)/ \
		$(MINIO_ALIAS)/$(MINIO_BUCKET)/$(BANK_ID)/
	@echo "Uploaded to $(MINIO_URL)/$(MINIO_BUCKET)/$(BANK_ID)/"

# ---------------------------------------------------------------------------
# 5. Tests
# ---------------------------------------------------------------------------
test:  ## Run E2E test suite (pytest tests/)
	$(PYTHON) -m pytest tests/ -v

# ---------------------------------------------------------------------------
# 6. Clean
# ---------------------------------------------------------------------------
clean:  ## Remove generated output and delivery directories
	rm -rf $(OUTPUT_DIR) $(DELIVERY_DIR)

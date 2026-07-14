#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U postgres -d icu_scheduling -f /scripts/mock_schema_scheduling.sql

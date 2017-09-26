#!/bin/bash

set -e

source prepare-shell.sh

CITATIONS_FILE=$DATA_PATH/crossref-works-citations.tsv.gz
CITATIONS_TEMP_FILE=$DATA_PATH/crossref-works-citations.tsv.gz.temp
CITATIONS_BACKUP_FILE=$DATA_PATH/crossref-works-citations.tsv.gz.backup

if [ -f "$CITATIONS_BACKUP_FILE" ]; then
  echo "Backup file already exists: $CITATIONS_BACKUP_FILE (please confirm and delete or rename it)"
  exit 1
fi

mkdir -p "$TEMP_DIR"

# print the header (the first line of input)
# and then run the specified command on the body (the rest of the input)
# use it in a pipeline, e.g. ps | body grep somepattern
body() {
  IFS= read -r header
  printf '%s\n' "$header"
  "$@"
}

gunzip -c "$CITATIONS_FILE" | pv | LC_ALL=C body sort -T "$TEMP_DIR" -u | gzip > "$CITATIONS_TEMP_FILE"

mv "$CITATIONS_FILE" "$CITATIONS_BACKUP_FILE"
mv "$CITATIONS_TEMP_FILE" "$CITATIONS_FILE"

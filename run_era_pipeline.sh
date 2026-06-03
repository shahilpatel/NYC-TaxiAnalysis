#!/bin/bash
# Load 2024/2019 BQ tables, run 5-arm SQL, export CSV, run analysis.
# Assumes parquet already in GCS (ingest/* and fhvhv/raw/*).
# Set GOOGLE_APPLICATION_CREDENTIALS before running.
cd "$(dirname "$0")"
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Set GOOGLE_APPLICATION_CREDENTIALS to your service account key path." >&2; exit 1
fi
gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS" >/dev/null 2>&1
P=pstat135-nyc-taxi
B=gs://pstat135-taxi-shahil

load_table () {   # $1=table  $2=uri_glob
  local tbl=$1 uri=$2
  echo ">> loading $tbl"
  if bq load --source_format=PARQUET --replace --autodetect "$P:taxi_analysis.$tbl" "$uri" 2>/tmp/load_$tbl.err; then
    echo "   bulk load ok"
  else
    echo "   bulk failed -> per-file:"; tail -2 /tmp/load_$tbl.err
    local first=1 flag
    for f in $(gsutil ls "$uri"); do
      if [ $first -eq 1 ]; then flag="--replace"; first=0; else flag="--noreplace"; fi
      if bq load --source_format=PARQUET $flag --autodetect "$P:taxi_analysis.$tbl" "$f" 2>>/tmp/load_$tbl.err; then
        echo "   + $(basename $f)"; else echo "   FAIL $(basename $f)"; fi
    done
  fi
}

load_table yellow_2024 "$B/ingest/yellow2024/*.parquet"
load_table fhvhv_2019  "$B/ingest/fhvhv2019/*.parquet"
load_table fhvhv_2024  "$B/fhvhv/raw/*.parquet"

echo "row counts:"
bq query --project_id=$P --use_legacy_sql=false --format=pretty \
'SELECT "yellow_2024" tbl, COUNT(*) n FROM `taxi_analysis.yellow_2024`
 UNION ALL SELECT "fhvhv_2019", COUNT(*) FROM `taxi_analysis.fhvhv_2019`
 UNION ALL SELECT "fhvhv_2024", COUNT(*) FROM `taxi_analysis.fhvhv_2024` ORDER BY tbl'

echo "running 5-arm aggregation..."
bq query --project_id=$P --use_legacy_sql=false --format=none < 10_era_compare.sql

echo "Manhattan share by arm:"
bq query --project_id=$P --use_legacy_sql=false --format=pretty \
'SELECT era, ROUND(100*SUM(IF(borough="Manhattan",trips,0))/SUM(trips),1) manhattan_pct,
        FORMAT("%d",SUM(trips)) trips, COUNT(DISTINCT zone_id) zones
 FROM `taxi_analysis.era_zone_period` GROUP BY era ORDER BY era'

echo "exporting CSV..."
bq query --project_id=$P --use_legacy_sql=false --format=csv --max_rows=20000 \
'SELECT era,period,zone_id,zone_name,borough,lat,lon,trips FROM `taxi_analysis.era_zone_period`
 ORDER BY era,period,zone_id' > era_zone_period.csv
echo "rows: $(wc -l < era_zone_period.csv)"

echo "running analysis..."
python3 11_era_cluster_compare.py
echo "done."

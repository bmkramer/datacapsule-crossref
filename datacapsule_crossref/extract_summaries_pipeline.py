from __future__ import absolute_import

import argparse
import logging

import apache_beam as beam
from apache_beam.io.filesystems import FileSystems
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions

from datacapsule_crossref.beam_utils.csv import (
  WriteDictCsv
)

from datacapsule_crossref.beam_utils.main import (
  add_cloud_args,
  process_cloud_args
)

from datacapsule_crossref.beam_utils.utils import (
  MapOrLog,
  FlatMapOrLog,
  TransformAndCount,
  TransformAndLog,
  PreventFusion,
  GroupTransforms
)

from datacapsule_crossref.utils.collection import (
  extend_dict
)

from datacapsule_crossref.doi_utils import clean_doi

from datacapsule_crossref.extract_citations_from_works import (
  extract_citations_from_work,
  flatten_citations,
  Columns as CitationsColumns,
  REGULAR_COLUMNS as CITATIONS_COLUMNS
)

from datacapsule_crossref.extract_summaries_from_works import (
  extract_summary_from_work,
  Columns as SummaryColumns,
  SUMMARY_COLUMNS
)

from datacapsule_crossref.reference_stats import (
  REFERENCE_STATS_COLUMNS
)

from datacapsule_crossref.csv_stats import (
  get_output_column_names as get_csv_stats_output_column_names
)

from datacapsule_crossref.extract_transforms import (
  ReferenceStatsCombineFn,
  CsvStatsCombineFn
)

from datacapsule_crossref.extract_utils import (
  find_zip_filenames_with_meta_file,
  read_works_from_zip,
  typed_counter_with_examples_to_dict
)

class MetricCounters(object):
  ZIP_TOTAL = 'zip_total_count'
  ZIP_PROCESSED = 'zip_processed_count'
  ZIP_ERROR = 'zip_error_count'

  WORK_TOTAL = 'work_total_count'

  WORK_CITATIONS_PROCESSED = 'work_citations_processed_count'
  WORK_CITATIONS_ERROR = 'work_citations_error_count'
  CITATIONS_OUTPUT = 'citations_output'

  WORK_SUMMARIES_PROCESSED = 'work_summaries_processed_count'
  WORK_SUMMARIES_ERROR = 'work_summaries_error_count'

def get_logger():
  return logging.getLogger(__name__)

def get_citations_columns(opt):
  citations_columns = list(CITATIONS_COLUMNS)
  if opt.citations_provenance:
    citations_columns += [CitationsColumns.PROVENANCE]
  if opt.citations_debug:
    citations_columns += [CitationsColumns.DEBUG]
  return citations_columns

def get_summary_columns(opt):
  summary_columns = list(SUMMARY_COLUMNS)
  if opt.summaries_provenance:
    summary_columns += [SummaryColumns.PROVENANCE]
  if opt.summaries_debug:
    summary_columns += [SummaryColumns.DEBUG]
  return summary_columns

def CitationsForWorks(opt, doi_filter):
  empty_link = opt.citations_empty_link
  citations_columns = get_citations_columns(opt)

  output_csv_prefix = FileSystems.join(opt.output_path, 'citations')
  get_logger().info('citations output_csv_prefix: %s', output_csv_prefix)

  return "CitationsForWorks" >> GroupTransforms(lambda p: (
    p |
    "ExtractCitations" >> TransformAndCount(
      MapOrLog(
        lambda (zip_filename, work): extend_dict(
          extract_citations_from_work(work, doi_filter),
          {CitationsColumns.PROVENANCE: zip_filename}
        ),
        error_count=MetricCounters.WORK_CITATIONS_ERROR
      ),
      MetricCounters.WORK_CITATIONS_PROCESSED
    ) |
    "FlattenCitations" >> TransformAndCount(
      beam.FlatMap(
        lambda citations: flatten_citations([citations], empty_link)
      ),
      MetricCounters.CITATIONS_OUTPUT
    ) |
    "WriteCitations" >> WriteDictCsv(
      output_csv_prefix,
      citations_columns,
      file_name_suffix='.tsv.gz'
    )
  ))

def ReferenceStatsForSummaries(opt):
  output_csv_prefix = FileSystems.join(opt.output_path, 'reference-stats')
  get_logger().info('reference stats output_csv_prefix: %s', output_csv_prefix)

  return "ReferenceStatsForSummaries" >> GroupTransforms(lambda p: (
    p |
    "CombineReferenceStats" >> TransformAndLog(
      beam.CombineGlobally(
        ReferenceStatsCombineFn()
      ),
      log_prefix='combined reference stats out: ',
      log_level='info'
    ) |
    "ConvertReferenceStatsToDict" >> beam.FlatMap(typed_counter_with_examples_to_dict) |
    "WriteReferenceStats" >> WriteDictCsv(
      output_csv_prefix,
      REFERENCE_STATS_COLUMNS,
      file_name_suffix='.tsv.gz',
      num_shards=1,
      shard_name_template=''
    )
  ))

def CsvStatsForSummaries(opt, name, groupby_columns):
  output_csv_prefix = FileSystems.join(opt.output_path, name)
  get_logger().info('csv stats output_csv_prefix: %s', output_csv_prefix)

  column_names = SUMMARY_COLUMNS
  csv_stats_columns = get_csv_stats_output_column_names(column_names, groupby_columns)

  return GroupTransforms(lambda p: (
    p |
    "CombineGeneralStats" >> TransformAndLog(
      beam.CombineGlobally(
        CsvStatsCombineFn(column_names, groupby_columns)
      ),
      log_prefix='csv reference stats out: ',
      log_level='info'
    ) |
    "FlattenResults" >> beam.FlatMap(lambda x: x) |
    "WriteCsvStats" >> WriteDictCsv(
      output_csv_prefix,
      csv_stats_columns,
      file_name_suffix='.tsv.gz',
      num_shards=1,
      shard_name_template=''
    )
  ))

def ExtractSummaryFromWorks(doi_filter):
  return "ExtractSummaryFromWorks" >> TransformAndCount(
    MapOrLog(
      lambda (zip_filename, work): extend_dict(
        extract_summary_from_work(work, doi_filter),
        {SummaryColumns.PROVENANCE: zip_filename}
      ),
      error_count=MetricCounters.WORK_SUMMARIES_ERROR
    ),
    MetricCounters.WORK_SUMMARIES_PROCESSED
  )

def WriteSummary(opt):
  summary_columns = get_summary_columns(opt)

  output_csv_prefix = FileSystems.join(opt.output_path, 'summaries')
  get_logger().info('summaries output_csv_prefix: %s', output_csv_prefix)

  return "WriteSummary" >> WriteDictCsv(
    output_csv_prefix,
    summary_columns,
    file_name_suffix='.tsv.gz'
  )

def GetZipFiles(opt):
  zip_filenames = find_zip_filenames_with_meta_file(opt.data_path)
  get_logger().info('found %d zip files', len(zip_filenames))
  get_logger().debug('zip files: %s', zip_filenames)
  assert zip_filenames

  return "GetZipFiles" >> TransformAndCount(
    beam.Create(zip_filenames),
    MetricCounters.ZIP_TOTAL
  )

def ReadWorksFromZip():
  return "ReadWorksFromZip" >> FlatMapOrLog(
    read_works_from_zip,
    error_count=MetricCounters.ZIP_ERROR,
    processed_count=MetricCounters.ZIP_PROCESSED,
    output_count=MetricCounters.WORK_TOTAL
  )

def configure_pipeline(p, opt):
  clean_doi_enabled = not opt.no_clean_dois
  doi_filter = clean_doi if clean_doi_enabled else lambda x: x

  works = (
    p |
    GetZipFiles(opt) |
    PreventFusion() |
    ReadWorksFromZip()
  )

  _ = (
    works |
    CitationsForWorks(opt, doi_filter)
  )

  summaries = works | ExtractSummaryFromWorks(doi_filter)

  _ = (
    summaries |
    ReferenceStatsForSummaries(opt)
  )

  _ = (
    summaries |
    "GeneralStats" >> CsvStatsForSummaries(opt, 'general-stats', None)
  )

  _ = (
    summaries |
    "GeneralStatsByTypeAndPublisher" >> CsvStatsForSummaries(
      opt, 'general-stats-by-type-and-publisher', [
        SummaryColumns.TYPE, SummaryColumns.PUBLISHER
    ])
  )

  _ = (
    summaries |
    WriteSummary(opt)
  )

def add_main_args(parser):
  source_group = parser.add_argument_group('source')
  source_group.add_argument(
    '--data-path', type=str, required=False,
    help='base data path'
  )

  output_group = parser.add_argument_group('output')
  output_group.add_argument(
    '--output-path', required=True,
    help='Output directory to write results to.'
  )

  summaries_group = parser.add_argument_group('summaries')
  summaries_group.add_argument(
    '--summaries-provenance', required=False,
    action='store_true',
    help='include provenance information (i.e. source filename)'
  )
  summaries_group.add_argument(
    '--summaries-debug', required=False,
    action='store_true',
    help='whether to include debug information'
  )

  citations_group = parser.add_argument_group('citations')
  summaries_group.add_argument(
    '--citations-provenance', required=False,
    action='store_true',
    help='include provenance information (i.e. source filename)'
  )
  citations_group.add_argument(
    '--citations-empty-link', required=False,
    action='store_true',
    help='whether to include an empty link where no citations are available'
  )
  citations_group.add_argument(
    '--citations-debug', required=False,
    action='store_true',
    help='whether to include debug information (implies empty-link)'
  )

  parser.add_argument(
    '--no-clean-dois', required=False,
    action='store_true',
    help='whether to disable DOI cleaning'
  )

  parser.add_argument(
    '--debug', action='store_true', default=False,
    help='enable debug output'
  )

def parse_args(argv=None):
  parser = argparse.ArgumentParser(
    description='Download Crossref Works data'
  )
  add_main_args(parser)
  add_cloud_args(parser)

  args = parser.parse_args(argv)

  if args.debug:
    logging.getLogger().setLevel('DEBUG')

  process_cloud_args(
    args, args.output_path,
    name='datacapsule-crossref-extract'
  )

  get_logger().info('args: %s', args)

  return args

def run(argv=None):
  args = parse_args(argv)

  # We use the save_main_session option because one or more DoFn's in this
  # workflow rely on global context (e.g., a module imported at module level).
  pipeline_options = PipelineOptions.from_dictionary(vars(args))
  pipeline_options.view_as(SetupOptions).save_main_session = True

  with beam.Pipeline(args.runner, options=pipeline_options) as p:
    configure_pipeline(p, args)

    # Execute the pipeline and wait until it is completed.


if __name__ == '__main__':
  logging.basicConfig(level='INFO')

  run()
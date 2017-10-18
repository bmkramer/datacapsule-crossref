import logging

import pandas as pd

from datacapsule_crossref.csv_stats import (
  calculate_counts_from_df_batches
)

def setup_module():
  logging.basicConfig(level='DEBUG')

class TestCalculateCountsFromDfBatches(object):
  def test_empty_df_should_produce_zero_counts(self):
    result = calculate_counts_from_df_batches([
      pd.DataFrame([], columns=['a', 'b'])
    ])
    assert result == {
      'count': [0, 0]
    }

  def test_should_count_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 10, 11]
    })])
    assert result['count'] == [4]

  def test_should_count_int_columns_without_nan(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, None, 11]
    })])
    assert result['count'] == [3]

  def test_should_count_bool_as_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': ['true', 'false', 'true', 'true']
    })])
    assert result['count'] == [4]
    assert result['count_non_zero'] == [3]
    assert result['count_zero'] == [1]

  def test_should_calculate_min_of_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 10, 11]
    })])
    assert result['min'] == [1]

  def test_should_calculate_max_of_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 10, 11]
    })])
    assert result['max'] == [11]

  def test_should_calculate_sum_of_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 10, 11]
    })])
    assert result['sum'] == [24]

  def test_should_calculate_mean_of_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 10, 11]
    })])
    assert result['mean'] == [24 / 4]

  def test_should_calculate_mean_including_zero_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 0, 11]
    })])
    assert result['mean'] == [14 / 4]

  def test_should_calculate_mean_of_non_zero_int_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': [1, 2, 0, 11]
    })])
    assert result['mean_non_zero'] == [14 / 3]

  def test_should_count_str_columns(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': ['a1', 'a2', 'a3', 'a4']
    })])
    assert result['count'] == [4]

  def test_should_count_str_columns_without_nan(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': ['a1', 'a2', pd.np.nan, 'a4']
    })])
    assert result['count'] == [3]

  def test_should_count_str_columns_containing_some_numbers(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': ['a1', 'a2', '3', 'a4']
    })])
    assert result['count'] == [4]

  def test_should_count_str_columns_containing_some_bool(self):
    result = calculate_counts_from_df_batches([pd.DataFrame({
      'a': ['a1', 'a2', 'false', 'a4']
    })])
    assert result['count'] == [4]
    assert 'count_non_zero' not in result

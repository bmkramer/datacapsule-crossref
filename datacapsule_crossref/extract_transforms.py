from apache_beam import CombineFn

from datacapsule_crossref.reference_stats import (
  TypedCounterWithExamples
)

from datacapsule_crossref.csv_stats import (
  CsvStats,
  get_output_column_names,
  flatten_stats
)

from datacapsule_crossref.extract_utils import (
  update_reference_counters_for_summary,
  dict_list_to_dataframe
)

class ReferenceStatsCombineFn(CombineFn):
  def create_accumulator(self, *args, **kwargs):
    return TypedCounterWithExamples(10)

  def add_input(self, accumulator, element, *args, **kwargs):
    """Return result of folding element into accumulator.

    CombineFn implementors must override add_input.

    Args:
      accumulator: the current accumulator
      element: the element to add
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    update_reference_counters_for_summary(accumulator, element)
    return accumulator

  def add_inputs(self, accumulator, elements, *args, **kwargs):
    """Returns the result of folding each element in elements into accumulator.

    This is provided in case the implementation affords more efficient
    bulk addition of elements. The default implementation simply loops
    over the inputs invoking add_input for each one.

    Args:
      accumulator: the current accumulator
      elements: the elements to add
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    for element in elements:
      accumulator = self.add_input(accumulator, element, *args, **kwargs)
    return accumulator

  def merge_accumulators(self, accumulators, *args, **kwargs):
    """Returns the result of merging several accumulators
    to a single accumulator value.

    Args:
      accumulators: the accumulators to merge
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    result = self.create_accumulator()
    for accumulator in accumulators:
      result.add_counter(accumulator)
    return result

  def extract_output(self, accumulator, *args, **kwargs):
    """Return result of converting accumulator into the output value.

    Args:
      accumulator: the final accumulator value computed by this CombineFn
        for the entire input key or PCollection.
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    return list(accumulator)

class CsvStatsCombineFn(CombineFn):
  def __init__(self, column_names, groupby_columns):
    self.column_names = column_names
    self.groupby_columns = groupby_columns
    super(CsvStatsCombineFn, self).__init__()

  def create_accumulator(self, *args, **kwargs):
    return CsvStats(self.groupby_columns)

  def add_input(self, accumulator, element, *args, **kwargs):
    """Return result of folding element into accumulator.

    CombineFn implementors must override add_input.

    Args:
      accumulator: the current accumulator
      element: the element to add
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    return self.add_inputs(accumulator, [element], *args, **kwargs)

  def add_inputs(self, accumulator, elements, *args, **kwargs):
    """Returns the result of folding each element in elements into accumulator.

    This is provided in case the implementation affords more efficient
    bulk addition of elements. The default implementation simply loops
    over the inputs invoking add_input for each one.

    Args:
      accumulator: the current accumulator
      elements: the elements to add
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    df = dict_list_to_dataframe(elements, self.column_names)
    accumulator.add_dataframe(df)
    return accumulator

  def merge_accumulators(self, accumulators, *args, **kwargs):
    """Returns the result of merging several accumulators
    to a single accumulator value.

    Args:
      accumulators: the accumulators to merge
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    result = self.create_accumulator()
    for accumulator in accumulators:
      result.add_stats(accumulator)
    return result

  def extract_output(self, accumulator, *args, **kwargs):
    """Return result of converting accumulator into the output value.

    Args:
      accumulator: the final accumulator value computed by this CombineFn
        for the entire input key or PCollection.
      *args: Additional arguments and side inputs.
      **kwargs: Additional arguments and side inputs.
    """
    return list(flatten_stats(
      accumulator.get_stats(), self.column_names, self.groupby_columns
    ))

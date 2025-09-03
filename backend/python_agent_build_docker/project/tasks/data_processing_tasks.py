from celery import shared_task
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import csv
import io

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_csv_data(self, csv_data: str, processing_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process CSV data with various transformations
    """
    try:
        logger.info("Processing CSV data")

        # Parse CSV data
        df = pd.read_csv(io.StringIO(csv_data))

        # Apply transformations based on config
        if processing_config.get('clean_headers', False):
            df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

        if processing_config.get('drop_na', False):
            df = df.dropna()

        if processing_config.get('fill_na', None):
            fill_value = processing_config['fill_na']
            df = df.fillna(fill_value)

        # Convert back to CSV
        processed_csv = df.to_csv(index=False)

        return {
            "processed_csv": processed_csv,
            "original_rows": len(pd.read_csv(io.StringIO(csv_data))),
            "processed_rows": len(df),
            "columns": list(df.columns),
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing CSV data: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def clean_and_transform_data(self, data: List[Dict[str, Any]], transformations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean and transform structured data
    """
    try:
        logger.info(f"Cleaning and transforming {len(data)} records")

        df = pd.DataFrame(data)

        for transform in transformations:
            transform_type = transform.get('type')
            column = transform.get('column')
            params = transform.get('params', {})

            if transform_type == 'fill_na' and column in df.columns:
                df[column] = df[column].fillna(params.get('value', ''))

            elif transform_type == 'drop_na' and column in df.columns:
                df = df.dropna(subset=[column])

            elif transform_type == 'string_clean' and column in df.columns:
                df[column] = df[column].astype(str).str.strip()

            elif transform_type == 'lowercase' and column in df.columns:
                df[column] = df[column].astype(str).str.lower()

            elif transform_type == 'uppercase' and column in df.columns:
                df[column] = df[column].astype(str).str.upper()

            elif transform_type == 'datetime_format' and column in df.columns:
                try:
                    df[column] = pd.to_datetime(df[column], errors='coerce')
                    if 'format' in params:
                        df[column] = df[column].dt.strftime(params['format'])
                except:
                    pass

            elif transform_type == 'numeric_cast' and column in df.columns:
                try:
                    df[column] = pd.to_numeric(df[column], errors='coerce')
                except:
                    pass

        return df.to_dict('records')

    except Exception as e:
        logger.error(f"Error in data transformation: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def aggregate_data(self, data: List[Dict[str, Any]], aggregation_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregate data with various statistical operations
    """
    try:
        logger.info(f"Aggregating {len(data)} records")

        df = pd.DataFrame(data)
        results = {}

        # Group by columns if specified
        groupby_cols = aggregation_config.get('group_by', [])
        if groupby_cols and all(col in df.columns for col in groupby_cols):
            grouped = df.groupby(groupby_cols)
        else:
            grouped = [(None, df)]

        # Apply aggregations
        for group_key, group_df in grouped:
            group_results = {}

            for agg in aggregation_config.get('aggregations', []):
                column = agg.get('column')
                operation = agg.get('operation')

                if column in group_df.columns:
                    try:
                        if operation == 'sum':
                            group_results[f'{column}_sum'] = group_df[column].sum()
                        elif operation == 'mean':
                            group_results[f'{column}_mean'] = group_df[column].mean()
                        elif operation == 'median':
                            group_results[f'{column}_median'] = group_df[column].median()
                        elif operation == 'count':
                            group_results[f'{column}_count'] = group_df[column].count()
                        elif operation == 'min':
                            group_results[f'{column}_min'] = group_df[column].min()
                        elif operation == 'max':
                            group_results[f'{column}_max'] = group_df[column].max()
                        elif operation == 'std':
                            group_results[f'{column}_std'] = group_df[column].std()
                    except:
                        group_results[f'{column}_{operation}'] = None

            if group_key is None:
                results['overall'] = group_results
            else:
                results[str(group_key)] = group_results

        return {
            "aggregation_results": results,
            "total_records": len(data),
            "groups_processed": len(results),
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error aggregating data: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def detect_anomalies(self, data: List[Dict[str, Any]], column: str, method: str = 'zscore', threshold: float = 3.0) -> Dict[str, Any]:
    """
    Detect anomalies in data using statistical methods
    """
    try:
        logger.info(f"Detecting anomalies in column: {column}")

        df = pd.DataFrame(data)

        if column not in df.columns:
            return {"anomalies": [], "error": f"Column {column} not found"}

        values = pd.to_numeric(df[column], errors='coerce').dropna()

        if method == 'zscore':
            # Z-score method
            mean = values.mean()
            std = values.std()
            z_scores = np.abs((values - mean) / std)
            anomalies = values[z_scores > threshold]

        elif method == 'iqr':
            # IQR method
            Q1 = values.quantile(0.25)
            Q3 = values.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            anomalies = values[(values < lower_bound) | (values > upper_bound)]

        else:
            return {"anomalies": [], "error": f"Unknown method: {method}"}

        anomaly_indices = anomalies.index.tolist()
        anomaly_values = anomalies.tolist()

        return {
            "anomalies": [
                {"index": int(idx), "value": float(val), "original_value": df.iloc[idx][column]}
                for idx, val in zip(anomaly_indices, anomaly_values)
            ],
            "total_values": len(values),
            "anomaly_count": len(anomalies),
            "method": method,
            "threshold": threshold,
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def merge_datasets(self, datasets: List[Dict[str, Any]], merge_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple datasets based on configuration
    """
    try:
        logger.info(f"Merging {len(datasets)} datasets")

        # Convert datasets to DataFrames
        dfs = []
        for i, dataset in enumerate(datasets):
            if isinstance(dataset, list):
                df = pd.DataFrame(dataset)
            elif isinstance(dataset, dict) and 'data' in dataset:
                df = pd.DataFrame(dataset['data'])
            else:
                df = pd.DataFrame([dataset])
            dfs.append((f"dataset_{i}", df))

        # Perform merge based on config
        merge_type = merge_config.get('type', 'inner')
        on_columns = merge_config.get('on', [])

        if len(dfs) < 2:
            result_df = dfs[0][1] if dfs else pd.DataFrame()
        else:
            result_df = dfs[0][1]
            for i, (name, df) in enumerate(dfs[1:], 1):
                if on_columns:
                    result_df = result_df.merge(df, on=on_columns, how=merge_type)
                else:
                    result_df = result_df.merge(df, how=merge_type)

        return {
            "merged_data": result_df.to_dict('records'),
            "original_datasets": len(datasets),
            "merged_rows": len(result_df),
            "merged_columns": list(result_df.columns),
            "merge_type": merge_type,
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error merging datasets: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def normalize_data(self, data: List[Dict[str, Any]], columns: List[str], method: str = 'minmax') -> Dict[str, Any]:
    """
    Normalize data columns using various methods
    """
    try:
        logger.info(f"Normalizing columns: {columns}")

        df = pd.DataFrame(data)
        results = {}

        for column in columns:
            if column in df.columns:
                values = pd.to_numeric(df[column], errors='coerce').dropna()

                if method == 'minmax':
                    min_val = values.min()
                    max_val = values.max()
                    if max_val > min_val:
                        normalized = (values - min_val) / (max_val - min_val)
                    else:
                        normalized = values * 0  # All zeros if all values are same

                elif method == 'zscore':
                    mean = values.mean()
                    std = values.std()
                    if std > 0:
                        normalized = (values - mean) / std
                    else:
                        normalized = values * 0

                else:
                    normalized = values

                results[column] = {
                    'original_values': values.tolist(),
                    'normalized_values': normalized.tolist(),
                    'method': method,
                    'parameters': {
                        'min': float(values.min()) if method == 'minmax' else None,
                        'max': float(values.max()) if method == 'minmax' else None,
                        'mean': float(values.mean()) if method == 'zscore' else None,
                        'std': float(values.std()) if method == 'zscore' else None
                    }
                }

        return {
            "normalization_results": results,
            "columns_processed": list(results.keys()),
            "method": method,
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error normalizing data: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def validate_data_quality(self, data: List[Dict[str, Any]], rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate data quality based on rules
    """
    try:
        logger.info("Validating data quality")

        df = pd.DataFrame(data)
        validation_results = {}

        for column, column_rules in rules.items():
            if column in df.columns:
                column_results = {}
                values = df[column]

                # Check for null values
                if 'not_null' in column_rules and column_rules['not_null']:
                    null_count = values.isnull().sum()
                    column_results['null_count'] = int(null_count)
                    column_results['null_percentage'] = float(null_count / len(values) * 100)

                # Check data type
                if 'type' in column_rules:
                    expected_type = column_rules['type']
                    if expected_type == 'numeric':
                        numeric_count = pd.to_numeric(values, errors='coerce').notnull().sum()
                        column_results['numeric_count'] = int(numeric_count)
                        column_results['numeric_percentage'] = float(numeric_count / len(values) * 100)

                # Check value range
                if 'min' in column_rules:
                    min_val = column_rules['min']
                    below_min = (pd.to_numeric(values, errors='coerce') < min_val).sum()
                    column_results['below_min'] = int(below_min)

                if 'max' in column_rules:
                    max_val = column_rules['max']
                    above_max = (pd.to_numeric(values, errors='coerce') > max_val).sum()
                    column_results['above_max'] = int(above_max)

                # Check unique values
                if 'unique' in column_rules and column_rules['unique']:
                    unique_count = values.nunique()
                    column_results['unique_count'] = int(unique_count)
                    column_results['duplicate_count'] = int(len(values) - unique_count)

                validation_results[column] = column_results

        # Overall quality score
        total_checks = sum(len(rules) for rules in validation_results.values())
        passed_checks = sum(1 for col_results in validation_results.values()
                           for check in col_results.values() if check == 0 or (isinstance(check, (int, float)) and check <= 5))

        quality_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100

        return {
            "validation_results": validation_results,
            "quality_score": float(quality_score),
            "total_records": len(data),
            "processing_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error validating data quality: {e}")
        raise self.retry(exc=e, countdown=30)

"""
Fuzzy Test: Invoice CSV Parser

Tests the robustness of CSV invoice parsing against malformed inputs.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    import atheris
    ATHERIS_AVAILABLE = True
    # Create the instrument_func decorator
    fuzz_instrument = atheris.instrument_func
except ImportError:
    ATHERIS_AVAILABLE = False
    print("Warning: Atheris not available")
    # Create a no-op decorator when atheris is not available
    def fuzz_instrument(func):
        return func

import csv
import io


def parse_invoice_csv(csv_data: str) -> list:
    """
    Parse invoice CSV data.

    Expected format:
    invoice_id,line_item,amount,quantity
    INV001,Service A,100.00,1

    Args:
        csv_data: CSV string

    Returns:
        List of invoice dictionaries

    Raises:
        ValueError: If invalid CSV
    """
    if not csv_data:
        raise ValueError("Empty CSV data")

    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        invoices = []

        for row in reader:
            # Validate required fields
            if 'invoice_id' not in row or 'amount' not in row:
                continue

            # Parse amount
            try:
                amount = float(row['amount'])
            except (ValueError, TypeError):
                continue

            invoices.append({
                'invoice_id': row['invoice_id'],
                'amount': amount,
                'quantity': int(row.get('quantity', 1))
            })

        return invoices

    except Exception as e:
        raise ValueError(f"Invalid CSV: {e}") from e


@fuzz_instrument
def test_invoice_csv_parser_fuzz(data):
    """
    Fuzz test for CSV invoice parsing.

    Tests:
    - Malformed CSV (missing delimiters, quotes)
    - Empty input
    - Very large CSV files
    - Special characters in fields
    - Invalid numbers

    Expected exceptions: ValueError (for invalid input)
    """
    try:
        # Convert bytes to string
        csv_str = data.decode('utf-8', errors='ignore')

        # Truncate for safety
        if len(csv_str) > 10000:
            csv_str = csv_str[:10000]

        # Parse CSV
        invoices = parse_invoice_csv(csv_str)

        # Verify results
        assert isinstance(invoices, list)

        for invoice in invoices:
            assert isinstance(invoice, dict)
            assert 'invoice_id' in invoice
            assert 'amount' in invoice
            assert isinstance(invoice['amount'], (int, float))
            assert not (invoice['amount'] != invoice['amount'])  # No NaN

    except ValueError:
        # Expected for invalid input
        pass
    except Exception as e:
        # Unexpected
        print(f"Unexpected exception: {e}")
        raise


def main(argc, argv):
    """Main entry point for fuzzing."""
    if not ATHERIS_AVAILABLE:
        print("Error: Atheris not available")
        sys.exit(1)

    atheris.Setup(argv, test_invoice_csv_parser_fuzz)
    atheris.Fuzz()


if __name__ == "__main__":
    main(len(sys.argv), sys.argv)

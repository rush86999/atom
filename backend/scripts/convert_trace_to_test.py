
import json
import os
import argparse
import sys

# Usage: python convert_trace_to_test.py --trace_id <UUID> --output_dir backend/tests/golden_dataset

def main():
    parser = argparse.ArgumentParser(description="Convert an Execution Trace to a Golden Test Case")
    parser.add_argument("--trace_id", required=True, help="UUID of the trace (filename without .json)")
    parser.add_argument("--trace_dir", default="backend/logs/traces", help="Directory containing traces")
    parser.add_argument("--output_dir", default="backend/tests/golden_dataset", help="Directory to save test case")
    
    args = parser.parse_args()
    
    trace_path = os.path.join(args.trace_dir, f"{args.trace_id}.json")
    if not os.path.exists(trace_path):
        print(f"Error: Trace file not found at {trace_path}")
        sys.exit(1)
        
    try:
        with open(trace_path, 'r') as f:
            trace = json.load(f)
            
        request_data = trace.get('request', {})
        result_data = trace.get('result', {})
        
        # Determine Input and Expected Output
        input_text = ""
        if isinstance(request_data, str):
            input_text = request_data
        elif isinstance(request_data, dict):
            input_text = request_data.get('text', '') or request_data.get('input', '')
            
        expected_answer = ""
        if isinstance(result_data, str):
            # Try to parse stringified JSON if possible
            try:
                res = json.loads(result_data)
                expected_answer = res.get('answer', '') or res.get('content', '')
            except:
                expected_answer = result_data
        elif isinstance(result_data, dict):
            expected_answer = result_data.get('answer', '') or result_data.get('content', '')
            
        if not input_text:
            print("Error: Could not extract input text from trace.")
            sys.exit(1)
            
        # Create Test Case Data
        test_case = {
            "id": args.trace_id,
            "input": input_text,
            "expected_output_fragment": expected_answer[:100], # Store partial for fuzzy match
            "full_expected_output": expected_answer,
            "trace_path": trace_path
        }
        
        # Save as JSON Test Data
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
            
        output_path = os.path.join(args.output_dir, f"test_{args.trace_id}.json")
        with open(output_path, 'w') as f:
            json.dump(test_case, f, indent=2)
            
        print(f"Success! Golden Test Case saved to: {output_path}")
        print(f"Input: {input_text}")
        print(f"Expected: {expected_answer[:50]}...")
        
    except Exception as e:
        print(f"Error processing trace: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

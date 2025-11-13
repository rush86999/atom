"""
WhatsApp Performance Benchmarking
API and database performance testing
"""

import time
import requests
import json
from datetime import datetime
import statistics

class WhatsAppPerformanceBenchmark:
    """Performance benchmarking for WhatsApp integration"""
    
    def __init__(self):
        self.base_url = "http://127.0.0.1:5058"
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'api_endpoints': {},
            'overall_metrics': {},
            'performance_grade': 'UNKNOWN'
        }
    
    def benchmark_api_endpoint(self, endpoint, name, iterations=10):
        """Benchmark API endpoint performance"""
        try:
            response_times = []
            success_count = 0
            
            for i in range(iterations):
                start_time = time.time()
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                    end_time = time.time()
                    
                    if response.status_code < 400:
                        response_times.append((end_time - start_time) * 1000)
                        success_count += 1
                except Exception as e:
                    logger.error(f"Benchmark error for {name}: {str(e)}")
            
            if response_times:
                avg_time = statistics.mean(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                median_time = statistics.median(response_times)
                
                self.results['api_endpoints'][name] = {
                    'average_response_time_ms': round(avg_time, 2),
                    'min_response_time_ms': round(min_time, 2),
                    'max_response_time_ms': round(max_time, 2),
                    'median_response_time_ms': round(median_time, 2),
                    'success_rate': f"{(success_count / iterations) * 100:.1f}%",
                    'iterations': iterations,
                    'grade': self.get_performance_grade(avg_time)
                }
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error benchmarking {name}: {str(e)}")
            return False
    
    def get_performance_grade(self, avg_response_time):
        """Get performance grade based on response time"""
        if avg_response_time < 100:
            return "A+ (Excellent)"
        elif avg_response_time < 200:
            return "A (Good)"
        elif avg_response_time < 500:
            return "B (Fair)"
        else:
            return "C (Poor)"
    
    def run_comprehensive_benchmark(self):
        """Run comprehensive performance benchmark"""
        print("⚡ WhatsApp Performance Benchmarking")
        print("=" * 40)
        
        # Benchmark key endpoints
        endpoints = [
            ("/api/whatsapp/health", "WhatsApp Health"),
            ("/api/whatsapp/conversations", "WhatsApp Conversations"),
            ("/api/whatsapp/analytics", "WhatsApp Analytics"),
            ("/ws/status", "WebSocket Status")
        ]
        
        success_count = 0
        
        for endpoint, name in endpoints:
            print(f"\n📊 Benchmarking: {name}")
            if self.benchmark_api_endpoint(endpoint, name):
                success_count += 1
                print(f"✅ {name}: COMPLETED")
            else:
                print(f"❌ {name}: FAILED")
        
        # Calculate overall metrics
        self.calculate_overall_metrics()
        
        # Print results
        self.print_benchmark_results()
        
        return success_count == len(endpoints)
    
    def calculate_overall_metrics(self):
        """Calculate overall performance metrics"""
        if not self.results['api_endpoints']:
            return
        
        response_times = []
        all_grades = []
        
        for endpoint_data in self.results['api_endpoints'].values():
            response_times.append(endpoint_data['average_response_time_ms'])
            all_grades.append(endpoint_data['grade'][0])  # Get the letter grade
        
        if response_times:
            self.results['overall_metrics'] = {
                'average_response_time_ms': round(statistics.mean(response_times), 2),
                'fastest_endpoint_ms': round(min(response_times), 2),
                'slowest_endpoint_ms': round(max(response_times), 2),
                'performance_grade': self.get_performance_grade(statistics.mean(response_times))
            }
    
    def print_benchmark_results(self):
        """Print benchmark results"""
        print("\n📊 Performance Benchmark Results")
        print("=" * 35)
        
        # Individual endpoint results
        for name, data in self.results['api_endpoints'].items():
            print(f"\n📋 {name}:")
            print(f"  📊 Avg Response: {data['average_response_time_ms']}ms")
            print(f"  ⚡ Min Response: {data['min_response_time_ms']}ms")
            print(f"  🐌 Max Response: {data['max_response_time_ms']}ms")
            print(f"  📈 Median Response: {data['median_response_time_ms']}ms")
            print(f"  ✅ Success Rate: {data['success_rate']}")
            print(f"  🏆 Grade: {data['grade']}")
        
        # Overall metrics
        if self.results['overall_metrics']:
            print(f"\n📈 Overall Performance:")
            metrics = self.results['overall_metrics']
            print(f"  📊 Average Response: {metrics['average_response_time_ms']}ms")
            print(f"  ⚡ Fastest Endpoint: {metrics['fastest_endpoint_ms']}ms")
            print(f"  🐌 Slowest Endpoint: {metrics['slowest_endpoint_ms']}ms")
            print(f"  🏆 Overall Grade: {metrics['performance_grade']}")
        
        # Performance targets
        print(f"\n🎯 Performance Targets:")
        if self.results['overall_metrics']:
            avg_time = self.results['overall_metrics']['average_response_time_ms']
            if avg_time < 200:
                print(f"  ✅ API Response Time: {avg_time}ms < 200ms (TARGET MET)")
            else:
                print(f"  ⚠️ API Response Time: {avg_time}ms > 200ms (TARGET NOT MET)")
        
        print(f"  🎯 Target: API < 200ms, DB < 100ms")
    
    def get_benchmark_results(self):
        """Get benchmark results"""
        return self.results

# Create global benchmark instance
performance_benchmark = WhatsAppPerformanceBenchmark()

# Export for use
__all__ = ['performance_benchmark', 'WhatsAppPerformanceBenchmark']

#!/usr/bin/env python3
"""
AI-Powered Integration System Executor
Advanced system with AI predictions and real-time dashboard
"""

import os
import sys
import json
import asyncio
import logging
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIIntegrationSystem:
    """AI-Powered Integration System Manager"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend/python-api-service"
        self.frontend_dir = self.project_root / "frontend-nextjs"
        self.processes = {}
        self.running = False
        self.startup_time = None
        
    def setup_environment(self):
        """Setup environment variables for AI system"""
        logger.info("🔧 Setting up AI-powered integration environment...")
        
        # Set environment variables
        env_vars = {
            'USE_BRIDGE_SYSTEM': 'true',
            'ENHANCED_HEALTH_MONITORING': 'true',
            'AI_ERROR_PREDICTION': 'true',
            'REALTIME_DASHBOARD': 'true',
            'FLASK_ENV': 'development',
            'PYTHONPATH': str(self.backend_dir),
            'PYTHON_API_SERVICE_BASE_URL': 'http://localhost:5058',
            'FASTAPI_BASE_URL': 'http://localhost:8001',
            'AI_MODEL_RETRAIN_INTERVAL': '24',  # hours
            'PREDICTION_THRESHOLD': '0.7',
            'ANOMALY_THRESHOLD': '-0.5',
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            logger.info(f"  {key}={value}")
        
        # Create necessary directories
        (self.backend_dir / "logs").mkdir(exist_ok=True)
        (self.backend_dir / "models").mkdir(exist_ok=True)
        (self.backend_dir / "reports").mkdir(exist_ok=True)
        
    def check_dependencies(self) -> bool:
        """Check if all AI system dependencies are available"""
        logger.info("📦 Checking AI system dependencies...")
        
        # Check required Python packages
        required_packages = [
            "flask", "httpx", "asyncpg", "aiofiles", 
            "python-dotenv", "pydantic", "fastapi",
            "scikit-learn", "numpy", "pandas", "joblib"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                if package == "scikit-learn":
                    __import__("sklearn")
                else:
                    __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"❌ Missing required packages: {missing_packages}")
            logger.info("Install with: pip install " + " ".join(missing_packages))
            return False
        
        # Check required files
        required_files = [
            "main_api_with_integrations.py",
            "enhanced_health_monitor.py",
            "enhanced_integration_service.py",
            "flask_fastapi_bridge.py",
            "enhanced_integration_routes.py",
            "ai_error_prediction.py",
            "realtime_dashboard.py",
            "ai_dashboard_api.py",
            "comprehensive_integration_tester.py",
        ]
        
        missing_files = []
        for file_name in required_files:
            file_path = self.backend_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            logger.error(f"❌ Missing required files: {missing_files}")
            return False
        
        logger.info("✅ All AI system dependencies satisfied")
        return True
    
    def start_backend_server(self) -> Optional[subprocess.Popen]:
        """Start AI-powered backend server"""
        logger.info("🚀 Starting AI-powered backend server...")
        
        cmd = [
            sys.executable, 
            "-m", 
            "flask", 
            "--app", 
            "main_api_with_integrations:create_app()", 
            "run", 
            "--host=0.0.0.0", 
            "--port=5058", 
            "--debug"
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=dict(os.environ)
            )
            
            # Give it time to start
            time.sleep(5)
            
            if process.poll() is None:
                logger.info("✅ AI-powered backend server started successfully")
                return process
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ Backend server failed to start: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to start backend server: {e}")
            return None
    
    async def run_ai_system_checks(self) -> Dict[str, Any]:
        """Run comprehensive AI system checks"""
        logger.info("🤖 Running AI system checks...")
        
        try:
            # Import AI components
            sys.path.append(str(self.backend_dir))
            from ai_error_prediction import get_ai_predictor
            from realtime_dashboard import get_dashboard
            
            predictor = get_ai_predictor()
            dashboard = get_dashboard()
            
            # Check AI models
            model_status = {
                "failure_predictor_loaded": predictor.failure_predictor is not None and predictor.failure_predictor != 'rule_based',
                "anomaly_detector_loaded": predictor.anomaly_detector is not None and predictor.anomaly_detector != 'rule_based',
                "scaler_loaded": predictor.scaler is not None,
                "model_version": predictor.model_version,
                "last_training_time": predictor.last_training_time,
                "training_data_size": len(predictor.training_data)
            }
            
            # Check dashboard
            dashboard_status = {
                "dashboard_initialized": dashboard is not None,
                "connected_clients": len(dashboard.connected_clients),
                "integration_metrics_count": len(dashboard.integration_metrics),
                "active_alerts": len([a for a in dashboard.alerts if not a.acknowledged]),
                "ai_predictions_count": len(dashboard.ai_predictions)
            }
            
            # Run quick training if needed
            training_needed = len(predictor.training_data) > 100
            if training_needed:
                logger.info("🧠 Training AI models with collected data...")
                training_success = await predictor.train_models()
                model_status["training_completed"] = training_success
            else:
                model_status["training_completed"] = "insufficient_data"
            
            return {
                "status": "completed",
                "model_status": model_status,
                "dashboard_status": dashboard_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ AI system checks failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def run_ai_predictions_demo(self) -> Dict[str, Any]:
        """Run AI predictions demonstration"""
        logger.info("🔮 Running AI predictions demonstration...")
        
        try:
            from ai_error_prediction import get_ai_predictor
            
            predictor = get_ai_predictor()
            
            # Create sample integration data
            sample_data = [
                {
                    "integration": "hubspot",
                    "service": "api",
                    "response_time": 1500,
                    "success_rate": 0.95,
                    "error_rate": 0.05,
                    "request_count": 100,
                    "consecutive_failures": 0,
                    "health_score_1h": 95.0,
                    "token_expires_hours": 24
                },
                {
                    "integration": "slack",
                    "service": "api", 
                    "response_time": 3000,
                    "success_rate": 0.80,
                    "error_rate": 0.20,
                    "request_count": 150,
                    "consecutive_failures": 3,
                    "health_score_1h": 75.0,
                    "token_expires_hours": 2
                },
                {
                    "integration": "jira",
                    "service": "api",
                    "response_time": 800,
                    "success_rate": 0.99,
                    "error_rate": 0.01,
                    "request_count": 50,
                    "consecutive_failures": 0,
                    "health_score_1h": 98.0,
                    "token_expires_hours": 48
                }
            ]
            
            # Run predictions
            predictions = []
            for data in sample_data:
                # Collect training data
                predictor.collect_training_data({
                    **data,
                    "failed": data.get("success_rate", 1.0) < 0.5
                })
                
                # Generate prediction
                prediction = await predictor.predict_failure(data)
                predictions.append({
                    "integration": data["integration"],
                    "prediction": {
                        "failure_probability": prediction.failure_probability,
                        "predicted_failure_type": prediction.predicted_failure_type,
                        "confidence": prediction.confidence,
                        "time_to_failure": prediction.time_to_failure,
                        "risk_factors": prediction.risk_factors,
                        "suggested_actions": prediction.suggested_actions
                    }
                })
            
            # Get system prediction
            system_prediction = await predictor.predict_system_health()
            
            return {
                "status": "completed",
                "individual_predictions": predictions,
                "system_prediction": {
                    "overall_risk_score": system_prediction.overall_risk_score,
                    "high_risk_integrations": system_prediction.high_risk_integrations,
                    "predicted_downtime_minutes": system_prediction.predicted_downtime_minutes,
                    "system_stability_trend": system_prediction.system_stability_trend,
                    "recommendations": system_prediction.recommendations
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ AI predictions demo failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def display_ai_system_info(self):
        """Display AI system information"""
        print(f"\n{'='*80}")
        print("🤖 AI-POWERED ATOM INTEGRATION SYSTEM")
        print(f"{'='*80}")
        print(f"🚀 Backend Server: http://localhost:5058")
        print(f"🤖 AI Dashboard: http://localhost:5058/api/v2/dashboard/")
        print(f"📊 System Health: http://localhost:5058/api/enhanced/health/overview")
        print(f"🔮 AI Predictions: http://localhost:5058/api/v2/dashboard/predictions")
        print(f"⚠️ Active Alerts: http://localhost:5058/api/v2/dashboard/alerts")
        print(f"🧠 Model Performance: http://localhost:5058/api/v2/dashboard/model/performance")
        print(f"📁 AI Models: {self.backend_dir}/models/")
        print(f"📄 Test Reports: {self.backend_dir}/reports/")
        print(f"⏰ Uptime: {time.time() - self.startup_time:.0f}s")
        print(f"\n🎯 AI Features:")
        print(f"  • Predictive Failure Detection")
        print(f"  • Real-time Anomaly Detection") 
        print(f"  • Intelligent Health Monitoring")
        print(f"  • Automated Resolution Suggestions")
        print(f"  • Performance Optimization")
        print(f"  • Multi-integration Risk Assessment")
        print(f"{'='*80}")
    
    def signal_handler(self, signum, frame):
        """Handle system signals"""
        logger.info(f"📡 Received signal {signum}")
        self.shutdown()
        sys.exit(0)
    
    async def run_complete_ai_system(self):
        """Run complete AI-powered integration system"""
        logger.info("🌟 Starting AI-Powered ATOM Integration System")
        self.startup_time = time.time()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Setup environment
            self.setup_environment()
            
            # Check dependencies
            if not self.check_dependencies():
                return False
            
            # Start backend server
            backend_process = self.start_backend_server()
            if not backend_process:
                logger.error("❌ Failed to start AI-powered backend server")
                return False
            
            self.processes["backend"] = backend_process
            
            # Wait for server to be ready
            logger.info("⏳ Waiting for AI server to be ready...")
            await asyncio.sleep(8)
            
            # Run AI system checks
            logger.info("🤖 Initializing AI systems...")
            ai_checks = await self.run_ai_system_checks()
            if ai_checks["status"] == "completed":
                logger.info("✅ AI systems initialized successfully")
            else:
                logger.warning("⚠️ Some AI systems failed to initialize")
            
            # Run AI predictions demo
            logger.info("🔮 Demonstrating AI predictions...")
            ai_demo = await self.run_ai_predictions_demo()
            if ai_demo["status"] == "completed":
                logger.info("✅ AI predictions demo completed successfully")
                
                # Display prediction results
                print(f"\n🔮 AI PREDICTION RESULTS")
                print(f"{'='*60}")
                for pred in ai_demo["individual_predictions"]:
                    integration = pred["integration"]
                    prediction = pred["prediction"]
                    
                    risk_level = "🔴 HIGH RISK" if prediction["failure_probability"] > 0.8 else \
                                "🟡 MEDIUM RISK" if prediction["failure_probability"] > 0.5 else "🟢 LOW RISK"
                    
                    print(f"\n{integration.upper()} Integration:")
                    print(f"  Risk Level: {risk_level}")
                    print(f"  Failure Probability: {prediction['failure_probability']:.1%}")
                    print(f"  Predicted Type: {prediction['predicted_failure_type']}")
                    print(f"  Time to Failure: {prediction['time_to_failure']} minutes" if prediction['time_to_failure'] else "  Time to Failure: N/A")
                    print(f"  Risk Factors: {', '.join(prediction['risk_factors'])}")
                    print(f"  Suggested Actions: {', '.join(prediction['suggested_actions'][:2])}...")
                
                print(f"\n🏢 SYSTEM PREDICTION:")
                sys_pred = ai_demo["system_prediction"]
                print(f"  Overall Risk Score: {sys_pred['overall_risk_score']:.1%}")
                print(f"  High Risk Integrations: {', '.join(sys_pred['high_risk_integrations'])}")
                print(f"  Predicted Downtime: {sys_pred['predicted_downtime_minutes']} minutes" if sys_pred['predicted_downtime_minutes'] else "  Predicted Downtime: N/A")
                print(f"  System Trend: {sys_pred['system_stability_trend']}")
                print(f"  Recommendations: {', '.join(sys_pred['recommendations'])}")
                print(f"{'='*60}")
                
            else:
                logger.warning("⚠️ AI predictions demo failed")
            
            # Start monitoring
            self.running = True
            logger.info("👀 Starting AI system monitoring (Ctrl+C to stop)...")
            
            # Display system information
            self.display_ai_system_info()
            
            # Monitor system
            while self.running:
                try:
                    # Log AI system status
                    uptime = time.time() - self.startup_time
                    logger.info(f"🤖 AI System uptime: {uptime:.0f}s - Running predictive monitoring...")
                    
                    # Check if backend is still running
                    if self.processes["backend"] and self.processes["backend"].poll() is not None:
                        logger.warning("⚠️ Backend process stopped, restarting...")
                        new_process = self.start_backend_server()
                        if new_process:
                            self.processes["backend"] = new_process
                    
                    # Sleep for monitoring interval
                    await asyncio.sleep(60)  # Check every minute
                    
                except KeyboardInterrupt:
                    logger.info("👋 Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"❌ Monitor error: {e}")
                    await asyncio.sleep(10)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ AI system startup failed: {e}")
            return False
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown AI system"""
        logger.info("🛑 Shutting down AI-Powered integration system...")
        
        self.running = False
        
        # Terminate all processes
        for name, process in self.processes.items():
            if process:
                logger.info(f"🛑 Stopping {name} process...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠️ Force killing {name} process...")
                    process.kill()
                except Exception as e:
                    logger.error(f"❌ Error stopping {name}: {e}")
        
        logger.info("✅ AI System shutdown complete")
        print(f"\n👋 AI-Powered ATOM Integration System stopped")

async def main():
    """Main entry point for AI system"""
    system = AIIntegrationSystem()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "demo":
            # Run AI predictions demo only
            ai_demo = await system.run_ai_predictions_demo()
            if ai_demo["status"] == "completed":
                print("✅ AI predictions demo completed successfully")
            else:
                print("❌ AI predictions demo failed")
                return False
        else:
            logger.error(f"❌ Unknown command: {command}")
            logger.info("Usage: python ai_integration_system.py [demo]")
            return False
    else:
        # Default: run complete AI system
        success = await system.run_complete_ai_system()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
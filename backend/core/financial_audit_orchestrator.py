"""
Financial Audit Orchestrator - Phase 94-05

Unified orchestration layer for all financial audit trail operations.

This service combines all audit validators and services to provide:
- Complete SOX compliance validation (all 5 AUD requirements)
- Comprehensive compliance reporting
- Audit trail export for external auditors
- Cross-model audit linking
- Health metrics for monitoring

Used by REST API and external audit systems.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from core.models import FinancialAudit
from core.audit_trail_validator import AuditTrailValidator
from core.chronological_integrity import ChronologicalIntegrityValidator
from core.hash_chain_integrity import HashChainIntegrity
from core.financial_audit_service import FinancialAuditService

logger = logging.getLogger(__name__)


class FinancialAuditOrchestrator:
    """
    Unified orchestration layer for financial audit trail operations.

    Combines all audit validators and services to provide:
    - Complete SOX compliance validation
    - Compliance reporting
    - Audit trail export
    - Cross-model audit linking

    Used by REST API and external audit systems.
    """

    def __init__(self, db: Session):
        """
        Initialize orchestrator with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db
        self.audit_validator = AuditTrailValidator(db)
        self.chron_validator = ChronologicalIntegrityValidator(db)
        self.hash_integrity = HashChainIntegrity(db)
        self.audit_service = FinancialAuditService()

    def validate_complete_compliance(
        self,
        account_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Run complete SOX compliance validation across all audit requirements.

        Validates:
        - AUD-01: Transaction logging completeness
        - AUD-02: Chronological integrity (monotonicity, no gaps)
        - AUD-03: Immutability (hash chain integrity)
        - AUD-04: SOX compliance (traceability, authorization, non-repudiation)
        - AUD-05: End-to-end traceability

        Args:
            account_id: Filter to specific account (optional)
            start_time: Start of validation window (optional)
            end_time: End of validation window (optional)

        Returns:
            Dict with complete compliance status and per-requirement results:
            - validated_at: str - ISO timestamp
            - account_id: Optional[str] - Account filtered
            - time_range: Dict - Start/end times
            - overall_compliant: bool - All requirements pass
            - requirements: Dict - Per-requirement results
            - summary: Dict - Requirement counts
        """
        results = {
            'validated_at': datetime.utcnow().isoformat(),
            'account_id': account_id,
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'overall_compliant': True,
            'requirements': {}
        }

        # AUD-01: Transaction logging completeness
        logger.info("Validating AUD-01: Transaction logging completeness")
        completeness = self.audit_validator.validate_completeness(
            start_time=start_time,
            end_time=end_time
        )
        results['requirements']['AUD-01'] = {
            'name': 'Transaction Logging Completeness',
            'description': 'All financial operations create audit entries',
            'compliant': completeness['complete'],
            'details': completeness
        }
        if not completeness['complete']:
            results['overall_compliant'] = False

        # AUD-02: Chronological integrity
        logger.info("Validating AUD-02: Chronological integrity")
        monotonicity = self.chron_validator.validate_monotonicity(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time
        )
        gaps = self.chron_validator.detect_gaps(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time
        )

        aud_02_compliant = monotonicity['is_monotonic'] and not gaps['has_gaps']
        results['requirements']['AUD-02'] = {
            'name': 'Chronological Integrity',
            'description': 'Timestamps are monotonic, sequence numbers have no gaps',
            'compliant': aud_02_compliant,
            'details': {
                'monotonicity': monotonicity,
                'gaps': gaps
            }
        }
        if not aud_02_compliant:
            results['overall_compliant'] = False

        # AUD-03: Immutability (hash chain integrity)
        logger.info("Validating AUD-03: Immutability and hash chain integrity")
        # If account_id specified, verify that account's chain
        # Otherwise, scan first 100 accounts for tampering
        if account_id:
            hash_verification = self.hash_integrity.verify_chain(account_id)
            hash_valid = hash_verification['is_valid']
        else:
            # Scan first 100 accounts for tampering
            tampering_scan = self.hash_integrity.detect_tampering(limit_accounts=100)
            hash_valid = len(tampering_scan['tampered_accounts']) == 0
            hash_verification = tampering_scan

        results['requirements']['AUD-03'] = {
            'name': 'Immutability and Hash Chain Integrity',
            'description': 'Audit entries cannot be modified, hash chains verify integrity',
            'compliant': hash_valid,
            'details': hash_verification
        }
        if not hash_valid:
            results['overall_compliant'] = False

        # AUD-04: SOX compliance (traceability, authorization, non-repudiation)
        logger.info("Validating AUD-04: SOX compliance requirements")
        required_fields = self.audit_validator.validate_required_fields(limit=1000)

        # For non-repudiation, check hash chain coverage
        sox_compliant = (
            required_fields['valid'] and
            hash_valid  # Hash chains provide non-repudiation
        )

        results['requirements']['AUD-04'] = {
            'name': 'SOX Compliance',
            'description': 'Traceability (3W2H), authorization tracking, non-repudiation',
            'compliant': sox_compliant,
            'details': {
                'required_fields': required_fields,
                'non_repudiation': hash_valid
            }
        }
        if not sox_compliant:
            results['overall_compliant'] = False

        # AUD-05: End-to-end traceability
        logger.info("Validating AUD-05: End-to-end audit trail verification")
        # Check if we can reconstruct audit trails
        # Sample reconstruction for first 10 accounts
        sample_accounts = self.db.query(FinancialAudit.account_id).distinct().limit(10).all()
        can_reconstruct = True
        reconstruction_samples = []

        for (account_id_sample,) in sample_accounts:
            try:
                trail = self.audit_service.get_full_audit_trail(self.db, account_id_sample)
                reconstruction_samples.append({
                    'account_id': account_id_sample,
                    'trail_length': len(trail),
                    'reconstructable': len(trail) > 0
                })
                if len(trail) == 0:
                    can_reconstruct = False
            except Exception as e:
                can_reconstruct = False
                reconstruction_samples.append({
                    'account_id': account_id_sample,
                    'error': str(e)
                })

        results['requirements']['AUD-05'] = {
            'name': 'End-to-End Audit Trail Verification',
            'description': 'Transactions can be reconstructed from audit logs',
            'compliant': can_reconstruct,
            'details': {
                'sample_accounts': len(sample_accounts),
                'reconstruction_samples': reconstruction_samples
            }
        }
        if not can_reconstruct:
            results['overall_compliant'] = False

        # Summary
        results['summary'] = {
            'total_requirements': 5,
            'compliant_requirements': sum(1 for r in results['requirements'].values() if r['compliant']),
            'non_compliant_requirements': sum(1 for r in results['requirements'].values() if not r['compliant']),
            'overall_compliant': results['overall_compliant']
        }

        return results

    def get_compliance_report(
        self,
        format: str = 'json'
    ) -> Dict[str, Any]:
        """
        Generate comprehensive SOX compliance report.

        Args:
            format: Output format ('json', 'summary', 'detailed')

        Returns:
            Compliance report with all audit metrics:
            - generated_at: str - ISO timestamp
            - report_type: str - Report type
            - format: str - Output format
            - statistics: Dict - Audit statistics
            - model_coverage: Dict - Model coverage
            - compliance: Dict - Compliance results
            - recommendations: List[str] - Actionable recommendations
        """
        # Get audit statistics
        stats = self.audit_validator.get_audit_statistics()

        # Get model coverage
        coverage = self.audit_validator.check_model_coverage()

        # Complete compliance validation
        compliance = self.validate_complete_compliance()

        # Build report
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'report_type': 'SOX_Compliance_Audit_Trail',
            'format': format,
            'statistics': stats,
            'model_coverage': coverage,
            'compliance': compliance,
            'recommendations': self._generate_recommendations(compliance)
        }

        if format == 'summary':
            # Simplified report
            report = {
                'generated_at': report['generated_at'],
                'overall_compliant': compliance['overall_compliant'],
                'total_audits': stats['total_audits'],
                'compliant_requirements': compliance['summary']['compliant_requirements'],
                'total_requirements': compliance['summary']['total_requirements'],
                'recommendations': report['recommendations']
            }

        return report

    def _generate_recommendations(self, compliance: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on compliance results.

        Args:
            compliance: Compliance validation results

        Returns:
            List of recommendation strings
        """
        recommendations = []

        for req_id, req_result in compliance['requirements'].items():
            if not req_result['compliant']:
                recommendations.append(
                    f"Fix {req_id}: {req_result['name']} - "
                    f"See details for specific issues"
                )

        if compliance['overall_compliant']:
            recommendations.append("All SOX audit requirements met. Continue monitoring.")

        return recommendations

    def generate_audit_trail_export(
        self,
        account_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        include_hash_chains: bool = True
    ) -> Dict[str, Any]:
        """
        Export audit trail for external auditors.

        Args:
            account_id: Filter to specific account (optional)
            start_time: Start of export range (optional)
            end_time: End of export range (optional)
            include_hash_chains: Include hash verification data (default True)

        Returns:
            Export data with audit entries and verification:
            - export_metadata: Dict - Export metadata
            - audit_entries: List[Dict] - Audit entries
            - verification: Optional[Dict] - Hash chain verification
        """
        query = self.db.query(FinancialAudit)

        if account_id:
            query = query.filter(FinancialAudit.account_id == account_id)
        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        audits = query.order_by(
            FinancialAudit.account_id,
            FinancialAudit.sequence_number
        ).all()

        # Build export data
        export_data = {
            'export_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'account_id': account_id,
                'time_range': {
                    'start': start_time.isoformat() if start_time else None,
                    'end': end_time.isoformat() if end_time else None
                },
                'total_entries': len(audits),
                'include_hash_chains': include_hash_chains
            },
            'audit_entries': [],
            'verification': None
        }

        # Add audit entries
        for audit in audits:
            entry = {
                'id': audit.id,
                'timestamp': audit.timestamp.isoformat(),
                'sequence_number': audit.sequence_number,
                'account_id': audit.account_id,
                'user_id': audit.user_id,
                'agent_id': audit.agent_id,
                'agent_maturity': audit.agent_maturity,
                'action_type': audit.action_type,
                'success': audit.success,
                'governance_check_passed': audit.governance_check_passed,
                'changes': audit.changes
            }

            if include_hash_chains:
                entry['integrity'] = {
                    'entry_hash': audit.entry_hash,
                    'prev_hash': audit.prev_hash
                }

            export_data['audit_entries'].append(entry)

        # Add hash chain verification if requested
        if include_hash_chains and account_id:
            verification = self.hash_integrity.verify_chain(account_id)
            export_data['verification'] = {
                'hash_chain_valid': verification['is_valid'],
                'break_count': verification['break_count'],
                'first_break': verification['first_break']
            }

        return export_data

    def get_audit_health_metrics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get audit health metrics for monitoring.

        Args:
            days: Number of days to analyze (default 30)

        Returns:
            Health metrics for SOX compliance monitoring:
            - period_days: int - Analysis period
            - period_start: str - ISO timestamp
            - period_end: str - ISO timestamp
            - health_score: int - 0-100 score
            - total_audits: int - Total audit entries
            - success_rate: float - Success percentage
            - issues_detected: Dict - Issue counts
            - recommendations: List[str] - Recommendations
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get recent audit stats
        stats = self.audit_validator.get_audit_statistics(
            start_time=cutoff,
            end_time=datetime.utcnow()
        )

        # Check for issues
        gaps = self.chron_validator.detect_gaps(
            start_time=cutoff,
            end_time=datetime.utcnow()
        )

        tampering = self.hash_integrity.detect_tampering(limit_accounts=1000)

        # Calculate health score
        health_issues = 0
        if gaps['has_gaps']:
            health_issues += gaps['total_gaps']
        if tampering['total_breaks'] > 0:
            health_issues += tampering['total_breaks']

        health_score = max(0, 100 - health_issues)

        return {
            'period_days': days,
            'period_start': cutoff.isoformat(),
            'period_end': datetime.utcnow().isoformat(),
            'health_score': health_score,
            'total_audits': stats['total_audits'],
            'success_rate': stats['success_rate'],
            'issues_detected': {
                'sequence_gaps': gaps['total_gaps'],
                'hash_chain_breaks': tampering['total_breaks'],
                'tampered_accounts': len(tampering['tampered_accounts'])
            },
            'recommendations': self._generate_recommendations(
                self.validate_complete_compliance()
            )
        }

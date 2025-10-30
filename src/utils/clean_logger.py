from src.utils.safe_logger import SafeLogger
from typing import Optional, Any, Dict, List
import sys
import traceback
import json

class CleanLogger:
    """
    Clean logging utility with professional tags instead of emojis
    """
    
    def __init__(self, name: str):
        self.logger = SafeLogger(name)
        self.module_name = name.split('.')[-1].upper()
    
    def _format_message(self, tag: str, message: str) -> str:
        """Format message with clean tag"""
        return f"[{tag}] {message}"
    
    def _format_exception(self, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None) -> str:
        """Create a structured exception message with stage, type, message, context, hints, and full traceback."""
        error_type = type(error).__name__
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        safe_context = context or {}
        safe_hints = hints or []
        try:
            context_str = json.dumps(safe_context, ensure_ascii=False)
        except Exception:
            context_str = str(safe_context)
        try:
            hints_str = json.dumps(safe_hints, ensure_ascii=False)
        except Exception:
            hints_str = str(safe_hints)
        return (
            f"Stage: {stage} | ErrorType: {error_type} | Message: {str(error)}\n"
            f"Context: {context_str}\nHints: {hints_str}\nTRACEBACK:\n{trace}"
        )
    
    # Workflow Tags
    def workflow_start(self, step: str, details: str = ""):
        """Log workflow step start"""
        msg = f"Starting {step}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("WORKFLOW", msg))
    
    def workflow_success(self, step: str, details: str = ""):
        """Log workflow step success"""
        msg = f"Completed {step}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("WORKFLOW", msg))
    
    def workflow_error(self, step: str, error: str):
        """Log workflow step error"""
        msg = f"Failed {step} - {error}"
        self.logger.error(self._format_message("WORKFLOW", msg))
    
    # Agent Tags
    def agent_start(self, agent_name: str, details: str = ""):
        """Log agent start"""
        msg = f"{agent_name} started"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("AGENT", msg))
    
    def agent_success(self, agent_name: str, details: str = ""):
        """Log agent success"""
        msg = f"{agent_name} completed"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("AGENT", msg))
    
    def agent_error(self, agent_name: str, error: str):
        """Log agent error"""
        msg = f"{agent_name} failed - {error}"
        self.logger.error(self._format_message("AGENT", msg))
    
    # Processing Tags
    def processing_start(self, process: str, details: str = ""):
        """Log processing start"""
        msg = f"Processing {process}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("PROCESSING", msg))
    
    def processing_success(self, process: str, details: str = ""):
        """Log processing success"""
        msg = f"Completed {process}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("PROCESSING", msg))
    
    def processing_error(self, process: str, error: str):
        """Log processing error"""
        msg = f"Failed {process} - {error}"
        self.logger.error(self._format_message("PROCESSING", msg))
    
    def processing_exception(self, process: str, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None):
        """Log processing exception with full traceback and context."""
        details = self._format_exception(stage=stage, error=error, context=context, hints=hints)
        self.logger.error(self._format_message("PROCESSING", details))
    
    # Data Tags
    def data_extracted(self, data_type: str, count: int, details: str = ""):
        """Log data extraction"""
        msg = f"Extracted {count} {data_type}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("DATA", msg))
    
    def data_validated(self, data_type: str, status: str, details: str = ""):
        """Log data validation"""
        msg = f"{data_type} validation: {status}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("DATA", msg))
    
    def data_stored(self, data_type: str, count: int, details: str = ""):
        """Log data storage"""
        msg = f"Stored {count} {data_type}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("DATA", msg))
    
    # LLM Tags
    def llm_request(self, model: str, prompt_type: str):
        """Log LLM request"""
        msg = f"Requesting {model} for {prompt_type}"
        self.logger.info(self._format_message("LLM", msg))
    
    def llm_response(self, model: str, status: str, details: str = ""):
        """Log LLM response"""
        msg = f"{model} response: {status}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("LLM", msg))
    
    def llm_error(self, model: str, error: str):
        """Log LLM error"""
        msg = f"{model} failed - {error}"
        self.logger.error(self._format_message("LLM", msg))
    
    # Storage Tags
    def storage_start(self, storage_type: str, details: str = ""):
        """Log storage start"""
        msg = f"Starting {storage_type} storage"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("STORAGE", msg))
    
    def storage_success(self, storage_type: str, count: int, details: str = ""):
        """Log storage success"""
        msg = f"Stored {count} {storage_type}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("STORAGE", msg))
    
    def storage_error(self, storage_type: str, error: str):
        """Log storage error"""
        msg = f"Failed {storage_type} storage - {error}"
        self.logger.error(self._format_message("STORAGE", msg))
    
    # Cache Tags
    def cache_save(self, cache_id: str, data_type: str):
        """Log cache save"""
        msg = f"Saved {data_type} with ID: {cache_id[:8]}..."
        self.logger.info(self._format_message("CACHE", msg))
    
    def cache_retrieve(self, cache_id: str, status: str):
        """Log cache retrieve"""
        msg = f"Retrieved cache {cache_id[:8]}... - {status}"
        self.logger.info(self._format_message("CACHE", msg))
    
    def cache_delete(self, cache_id: str):
        """Log cache delete"""
        msg = f"Deleted cache {cache_id[:8]}..."
        self.logger.info(self._format_message("CACHE", msg))
    
    # Validation Tags
    def validation_start(self, validation_type: str):
        """Log validation start"""
        msg = f"Starting {validation_type} validation"
        self.logger.info(self._format_message("VALIDATION", msg))
    
    def validation_result(self, validation_type: str, result: str, confidence: Optional[float] = None):
        """Log validation result"""
        msg = f"{validation_type} validation: {result}"
        if confidence is not None:
            msg += f" (confidence: {confidence:.2f})"
        self.logger.info(self._format_message("VALIDATION", msg))
    
    def validation_error(self, validation_type: str, error: str):
        """Log validation error"""
        msg = f"{validation_type} validation failed - {error}"
        self.logger.error(self._format_message("VALIDATION", msg))
    
    # Analysis Tags
    def analysis_start(self, analysis_type: str):
        """Log analysis start"""
        msg = f"Starting {analysis_type} analysis"
        self.logger.info(self._format_message("ANALYSIS", msg))
    
    def analysis_result(self, analysis_type: str, metrics: list, details: str = ""):
        """Log analysis result"""
        msg = f"{analysis_type} analysis completed - {len(metrics)} metrics detected"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("ANALYSIS", msg))
    
    def analysis_error(self, analysis_type: str, error: str):
        """Log analysis error"""
        msg = f"{analysis_type} analysis failed - {error}"
        self.logger.error(self._format_message("ANALYSIS", msg))
    
    def analysis_exception(self, analysis_type: str, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None):
        """Log analysis exception with full traceback and context."""
        details = self._format_exception(stage=stage, error=error, context=context, hints=hints)
        self.logger.error(self._format_message("ANALYSIS", details))
    
    # Graph Tags
    def graph_generation(self, chart_count: int, chart_types: list):
        """Log graph generation"""
        msg = f"Generated {chart_count} charts: {', '.join(chart_types)}"
        self.logger.info(self._format_message("GRAPH", msg))
    
    def graph_error(self, error: str):
        """Log graph error"""
        msg = f"Graph generation failed - {error}"
        self.logger.error(self._format_message("GRAPH", msg))
    
    def graph_exception(self, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None):
        """Log graph exception with full traceback and context."""
        details = self._format_exception(stage=stage, error=error, context=context, hints=hints)
        self.logger.error(self._format_message("GRAPH", details))
    
    def graph_fallback(self, reason: str):
        """Log graph fallback usage"""
        msg = f"Using fallback charts - {reason}"
        self.logger.warning(self._format_message("GRAPH", msg))
    
    # File Processing Tags
    def file_upload(self, filename: str, size: int):
        """Log file upload"""
        msg = f"Uploaded {filename} ({size} bytes)"
        self.logger.info(self._format_message("FILE", msg))
    
    def file_validation(self, filename: str, status: str, details: str = ""):
        """Log file validation"""
        msg = f"{filename} validation: {status}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("FILE", msg))
    
    def file_error(self, filename: str, error: str):
        """Log file processing error"""
        msg = f"{filename} processing failed - {error}"
        self.logger.error(self._format_message("FILE", msg))
    
    def file_exception(self, filename: str, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None):
        """Log file exception with full traceback and context."""
        details = self._format_exception(stage=stage, error=error, context=context, hints=hints)
        self.logger.error(self._format_message("FILE", details))
    
    def file_extraction(self, filename: str, content_type: str, size: int):
        """Log file content extraction"""
        msg = f"Extracted {content_type} from {filename} ({size} chars)"
        self.logger.info(self._format_message("FILE", msg))
    
    # Database Tags
    def db_connection(self, db_type: str, status: str):
        """Log database connection"""
        msg = f"{db_type} connection: {status}"
        self.logger.info(self._format_message("DATABASE", msg))
    
    def db_query(self, query_type: str, table: str, count: int = 0):
        """Log database query"""
        msg = f"{query_type} on {table}"
        if count > 0:
            msg += f" - {count} records"
        self.logger.info(self._format_message("DATABASE", msg))
    
    def db_error(self, operation: str, error: str):
        """Log database error"""
        msg = f"{operation} failed - {error}"
        self.logger.error(self._format_message("DATABASE", msg))
    
    def db_insert(self, table: str, count: int, details: str = ""):
        """Log database insert"""
        msg = f"Inserted {count} records into {table}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("DATABASE", msg))
    
    # Performance Tags
    def performance_start(self, operation: str):
        """Log performance measurement start"""
        msg = f"Starting performance measurement for {operation}"
        self.logger.info(self._format_message("PERFORMANCE", msg))
    
    def performance_result(self, operation: str, duration: float, details: str = ""):
        """Log performance measurement result"""
        msg = f"{operation} completed in {duration:.2f}s"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("PERFORMANCE", msg))
    
    def performance_warning(self, operation: str, duration: float, threshold: float):
        """Log performance warning"""
        msg = f"{operation} took {duration:.2f}s (threshold: {threshold:.2f}s)"
        self.logger.warning(self._format_message("PERFORMANCE", msg))
    
    # Security Tags
    def security_check(self, check_type: str, status: str, details: str = ""):
        """Log security check"""
        msg = f"{check_type} security check: {status}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("SECURITY", msg))
    
    def security_warning(self, warning_type: str, details: str):
        """Log security warning"""
        msg = f"{warning_type} security warning - {details}"
        self.logger.warning(self._format_message("SECURITY", msg))
    
    def security_error(self, error_type: str, error: str):
        """Log security error"""
        msg = f"{error_type} security error - {error}"
        self.logger.error(self._format_message("SECURITY", msg))
    
    # API Tags
    def api_request(self, endpoint: str, method: str, status_code: int = 0):
        """Log API request"""
        msg = f"{method} {endpoint}"
        if status_code > 0:
            msg += f" - {status_code}"
        self.logger.info(self._format_message("API", msg))
    
    def api_response(self, endpoint: str, status_code: int, duration: float = 0):
        """Log API response"""
        msg = f"{endpoint} responded with {status_code}"
        if duration > 0:
            msg += f" ({duration:.2f}s)"
        self.logger.info(self._format_message("API", msg))
    
    def api_error(self, endpoint: str, error: str, status_code: int = 0):
        """Log API error"""
        msg = f"{endpoint} failed"
        if status_code > 0:
            msg += f" ({status_code})"
        msg += f" - {error}"
        self.logger.error(self._format_message("API", msg))
    
    # Rate Limiting Tags
    def rate_limit(self, endpoint: str, limit: str, current: int):
        """Log rate limiting"""
        msg = f"{endpoint} rate limit: {current}/{limit}"
        self.logger.info(self._format_message("RATE_LIMIT", msg))
    
    def rate_limit_exceeded(self, endpoint: str, limit: str):
        """Log rate limit exceeded"""
        msg = f"{endpoint} rate limit exceeded ({limit})"
        self.logger.warning(self._format_message("RATE_LIMIT", msg))
    
    # Configuration Tags
    def config_load(self, config_type: str, status: str, details: str = ""):
        """Log configuration loading"""
        msg = f"{config_type} configuration: {status}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("CONFIG", msg))
    
    def config_error(self, config_type: str, error: str):
        """Log configuration error"""
        msg = f"{config_type} configuration failed - {error}"
        self.logger.error(self._format_message("CONFIG", msg))
    
    # Metrics Tags
    def metrics_collect(self, metric_name: str, value: Any, unit: str = ""):
        """Log metrics collection"""
        msg = f"Collected {metric_name}: {value}"
        if unit:
            msg += f" {unit}"
        self.logger.info(self._format_message("METRICS", msg))
    
    def metrics_threshold(self, metric_name: str, value: Any, threshold: Any, unit: str = ""):
        """Log metrics threshold"""
        msg = f"{metric_name} threshold: {value}/{threshold}"
        if unit:
            msg += f" {unit}"
        self.logger.warning(self._format_message("METRICS", msg))
    
    # Chunking Tags
    def chunking_start(self, content_type: str, size: int):
        """Log chunking start"""
        msg = f"Starting chunking for {content_type} ({size} chars)"
        self.logger.info(self._format_message("CHUNKING", msg))
    
    def chunking_result(self, chunk_count: int, total_tokens: int, details: str = ""):
        """Log chunking result"""
        msg = f"Created {chunk_count} chunks ({total_tokens} tokens)"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("CHUNKING", msg))
    
    def chunking_error(self, error: str):
        """Log chunking error"""
        msg = f"Chunking failed - {error}"
        self.logger.error(self._format_message("CHUNKING", msg))
    
    # Embedding Tags
    def embedding_start(self, chunk_count: int):
        """Log embedding start"""
        msg = f"Starting embedding for {chunk_count} chunks"
        self.logger.info(self._format_message("EMBEDDING", msg))
    
    def embedding_result(self, embedded_count: int, total_count: int):
        """Log embedding result"""
        msg = f"Embedded {embedded_count}/{total_count} chunks"
        self.logger.info(self._format_message("EMBEDDING", msg))
    
    def embedding_error(self, error: str):
        """Log embedding error"""
        msg = f"Embedding failed - {error}"
        self.logger.error(self._format_message("EMBEDDING", msg))
    
    # Cross-Report Tags
    def cross_report_start(self, report_count: int):
        """Log cross-report analysis start"""
        msg = f"Starting cross-report analysis for {report_count} reports"
        self.logger.info(self._format_message("CROSS_REPORT", msg))
    
    def cross_report_result(self, suggestions_count: int, details: str = ""):
        """Log cross-report analysis result"""
        msg = f"Generated {suggestions_count} cross-report suggestions"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("CROSS_REPORT", msg))
    
    def cross_report_error(self, error: str):
        """Log cross-report analysis error"""
        msg = f"Cross-report analysis failed - {error}"
        self.logger.error(self._format_message("CROSS_REPORT", msg))
    
    def cross_report_exception(self, stage: str, error: Exception, context: Optional[Dict[str, Any]] = None, hints: Optional[List[str]] = None):
        """Log cross-report exception with full traceback and context."""
        details = self._format_exception(stage=stage, error=error, context=context, hints=hints)
        self.logger.error(self._format_message("CROSS_REPORT", details))
    
    # Timeout Tags
    def timeout_warning(self, operation: str, duration: float, limit: float):
        """Log timeout warning"""
        msg = f"{operation} approaching timeout ({duration:.2f}s/{limit:.2f}s)"
        self.logger.warning(self._format_message("TIMEOUT", msg))
    
    def timeout_error(self, operation: str, limit: float):
        """Log timeout error"""
        msg = f"{operation} timed out after {limit:.2f}s"
        self.logger.error(self._format_message("TIMEOUT", msg))
    
    # Memory Tags
    def memory_usage(self, operation: str, usage: str, details: str = ""):
        """Log memory usage"""
        msg = f"{operation} memory usage: {usage}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("MEMORY", msg))
    
    def memory_warning(self, operation: str, usage: str, threshold: str):
        """Log memory warning"""
        msg = f"{operation} high memory usage: {usage} (threshold: {threshold})"
        self.logger.warning(self._format_message("MEMORY", msg))
    
    # Cleanup Tags
    def cleanup_start(self, cleanup_type: str, target: str):
        """Log cleanup start"""
        msg = f"Starting {cleanup_type} cleanup for {target}"
        self.logger.info(self._format_message("CLEANUP", msg))
    
    def cleanup_result(self, cleanup_type: str, count: int, details: str = ""):
        """Log cleanup result"""
        msg = f"{cleanup_type} cleanup completed - {count} items"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("CLEANUP", msg))
    
    def cleanup_error(self, cleanup_type: str, error: str):
        """Log cleanup error"""
        msg = f"{cleanup_type} cleanup failed - {error}"
        self.logger.error(self._format_message("CLEANUP", msg))
    
    # Generic methods for backward compatibility
    def info(self, message: str):
        """Generic info log"""
        self.logger.info(self._format_message(self.module_name, message))
    
    def warning(self, message: str):
        """Generic warning log"""
        self.logger.warning(self._format_message(self.module_name, message))
    
    def error(self, message: str):
        """Generic error log"""
        self.logger.error(self._format_message(self.module_name, message))
    
    def debug(self, message: str):
        """Generic debug log"""
        self.logger.debug(self._format_message(self.module_name, message))
    
    # Utility Methods
    def log_step(self, step_number: int, total_steps: int, step_name: str, details: str = ""):
        """Log a numbered step in a process"""
        msg = f"Step {step_number}/{total_steps}: {step_name}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("STEP", msg))
    
    def log_progress(self, current: int, total: int, operation: str, details: str = ""):
        """Log progress for an operation"""
        percentage = (current / total) * 100 if total > 0 else 0
        msg = f"{operation} progress: {current}/{total} ({percentage:.1f}%)"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("PROGRESS", msg))
    
    def log_retry(self, operation: str, attempt: int, max_attempts: int, reason: str = ""):
        """Log retry attempt"""
        msg = f"{operation} retry attempt {attempt}/{max_attempts}"
        if reason:
            msg += f" - {reason}"
        self.logger.warning(self._format_message("RETRY", msg))
    
    def log_skip(self, operation: str, reason: str):
        """Log skipped operation"""
        msg = f"Skipped {operation} - {reason}"
        self.logger.warning(self._format_message("SKIP", msg))
    
    def log_decision(self, decision: str, context: str, details: str = ""):
        """Log a decision made by the system"""
        msg = f"Decision: {decision} for {context}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("DECISION", msg))
    
    def log_route(self, from_step: str, to_step: str, reason: str = ""):
        """Log workflow routing decision"""
        msg = f"Routing from {from_step} to {to_step}"
        if reason:
            msg += f" - {reason}"
        self.logger.info(self._format_message("ROUTE", msg))
    
    def log_condition(self, condition: str, result: bool, details: str = ""):
        """Log condition evaluation"""
        msg = f"Condition '{condition}': {result}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("CONDITION", msg))
    
    def log_state_change(self, from_state: str, to_state: str, trigger: str = ""):
        """Log state change"""
        msg = f"State changed from {from_state} to {to_state}"
        if trigger:
            msg += f" (triggered by: {trigger})"
        self.logger.info(self._format_message("STATE", msg))
    
    def log_batch_start(self, batch_type: str, count: int, details: str = ""):
        """Log batch operation start"""
        msg = f"Starting {batch_type} batch processing for {count} items"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("BATCH", msg))
    
    def log_batch_result(self, batch_type: str, processed: int, total: int, details: str = ""):
        """Log batch operation result"""
        msg = f"{batch_type} batch completed: {processed}/{total} processed"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("BATCH", msg))
    
    def log_batch_error(self, batch_type: str, error: str):
        """Log batch operation error"""
        msg = f"{batch_type} batch failed - {error}"
        self.logger.error(self._format_message("BATCH", msg))
    
    def log_export(self, export_type: str, format: str, count: int, destination: str = ""):
        """Log data export"""
        msg = f"Exported {count} {export_type} in {format} format"
        if destination:
            msg += f" to {destination}"
        self.logger.info(self._format_message("EXPORT", msg))
    
    def log_import(self, import_type: str, format: str, count: int, source: str = ""):
        """Log data import"""
        msg = f"Imported {count} {import_type} from {format} format"
        if source:
            msg += f" from {source}"
        self.logger.info(self._format_message("IMPORT", msg))
    
    def log_sync(self, sync_type: str, status: str, count: int = 0, details: str = ""):
        """Log synchronization operation"""
        msg = f"{sync_type} sync: {status}"
        if count > 0:
            msg += f" ({count} items)"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("SYNC", msg))
    
    def log_backup(self, backup_type: str, status: str, size: str = "", details: str = ""):
        """Log backup operation"""
        msg = f"{backup_type} backup: {status}"
        if size:
            msg += f" ({size})"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("BACKUP", msg))
    
    def log_restore(self, restore_type: str, status: str, source: str = "", details: str = ""):
        """Log restore operation"""
        msg = f"{restore_type} restore: {status}"
        if source:
            msg += f" from {source}"
        if details:
            msg += f" - {details}"
        self.logger.info(self._format_message("RESTORE", msg))


# Convenience function to create clean logger
def get_clean_logger(name: str) -> CleanLogger:
    """Get a clean logger instance"""
    return CleanLogger(name)


# Context manager for automatic performance logging
class PerformanceLogger:
    """Context manager for automatic performance logging"""
    
    def __init__(self, logger: CleanLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.performance_start(self.operation)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        if self.start_time:
            duration = time.time() - self.start_time
            if exc_type is None:
                self.logger.performance_result(self.operation, duration)
            else:
                self.logger.performance_result(self.operation, duration, f"with error: {exc_val}")


# Decorator for automatic method logging
def log_method_calls(logger: CleanLogger, method_name: str = None):
    """Decorator to automatically log method calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = method_name or func.__name__
            logger.info(f"Calling {name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"{name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{name} failed - {str(e)}")
                raise
        return wrapper
    return decorator

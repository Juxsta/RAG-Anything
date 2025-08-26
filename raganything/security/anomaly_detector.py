"""
Security anomaly detection system for RAG-Anything.

This module implements various anomaly detection techniques:
- Statistical anomaly detection
- Behavioral pattern analysis
- Temporal anomaly detection
- Geolocation-based detection
- Machine learning-based detection
"""

import json
import time
import math
import statistics
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import redis.asyncio as aioredis
import logging

# Configure logger
logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of security anomalies"""
    STATISTICAL_OUTLIER = "statistical_outlier"
    BEHAVIORAL_CHANGE = "behavioral_change"
    TEMPORAL_ANOMALY = "temporal_anomaly"
    VOLUME_ANOMALY = "volume_anomaly"
    PATTERN_ANOMALY = "pattern_anomaly"
    GEOLOCATION_ANOMALY = "geo_anomaly"
    VELOCITY_ANOMALY = "velocity_anomaly"
    CREDENTIAL_ANOMALY = "credential_anomaly"


class AnomalySeverity(Enum):
    """Severity levels for anomalies"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityAnomaly:
    """Security anomaly detection result"""
    
    # Basic anomaly information
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    score: float  # 0.0 to 1.0, higher is more anomalous
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Context
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    
    # Detection details
    description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    baseline_data: Dict[str, Any] = field(default_factory=dict)
    current_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    detection_model: str = ""
    confidence: float = 0.0
    false_positive_likelihood: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert anomaly to dictionary"""
        return {
            'anomaly_id': self._generate_id(),
            'anomaly_type': self.anomaly_type.value,
            'severity': self.severity.value,
            'score': self.score,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'session_id': self.session_id,
            'description': self.description,
            'evidence': self.evidence,
            'baseline_data': self.baseline_data,
            'current_data': self.current_data,
            'detection_model': self.detection_model,
            'confidence': self.confidence,
            'false_positive_likelihood': self.false_positive_likelihood
        }
    
    def _generate_id(self) -> str:
        """Generate unique anomaly ID"""
        import hashlib
        content = f"{self.timestamp.isoformat()}{self.anomaly_type.value}{self.user_id or ''}{self.ip_address or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class DetectionConfig:
    """Configuration for anomaly detection"""
    
    # General settings
    enable_detection: bool = True
    detection_window_hours: int = 24
    baseline_window_days: int = 30
    min_baseline_samples: int = 10
    
    # Statistical thresholds
    statistical_threshold: float = 2.5  # Standard deviations
    volume_threshold_multiplier: float = 3.0
    velocity_threshold_kmh: float = 1000.0  # Impossible travel speed
    
    # Behavioral thresholds
    behavioral_change_threshold: float = 0.7  # Cosine similarity
    pattern_deviation_threshold: float = 0.8
    
    # Time-based settings
    normal_hours_start: int = 6  # 6 AM
    normal_hours_end: int = 22  # 10 PM
    weekend_penalty_factor: float = 1.5
    
    # Geolocation settings
    max_location_change_km: float = 500.0
    min_time_between_locations_minutes: int = 30
    
    # Redis settings
    redis_prefix: str = "raganything:anomaly"
    cache_ttl: int = 7 * 24 * 3600  # 7 days
    
    # Alert thresholds
    alert_score_threshold: float = 0.7
    alert_consecutive_threshold: int = 3


class BaseAnomalyDetector:
    """Base class for anomaly detectors"""
    
    def __init__(self, config: DetectionConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self.model_name = self.__class__.__name__
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]], 
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """Detect anomalies in a batch of events"""
        raise NotImplementedError
    
    async def _get_baseline_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get baseline data from cache"""
        try:
            if self.redis_client:
                cache_key = f"{self.config.redis_prefix}:baseline:{key}"
                data = await self.redis_client.get(cache_key)
                if data:
                    return json.loads(data)
        except Exception as e:
            logger.warning(f"Error getting baseline data: {e}")
        return None
    
    async def _set_baseline_data(self, key: str, data: Dict[str, Any]) -> None:
        """Store baseline data in cache"""
        try:
            if self.redis_client:
                cache_key = f"{self.config.redis_prefix}:baseline:{key}"
                await self.redis_client.setex(
                    cache_key, 
                    self.config.cache_ttl, 
                    json.dumps(data)
                )
        except Exception as e:
            logger.warning(f"Error setting baseline data: {e}")


class StatisticalAnomalyDetector(BaseAnomalyDetector):
    """Detects statistical outliers in user behavior"""
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]], 
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """Detect statistical anomalies"""
        anomalies = []
        
        # Group events by user
        user_events = defaultdict(list)
        for event in events:
            if event.get('user_id'):
                user_events[event['user_id']].append(event)
        
        for user_id, user_event_list in user_events.items():
            user_anomalies = await self._detect_user_statistical_anomalies(user_id, user_event_list)
            anomalies.extend(user_anomalies)
        
        return anomalies
    
    async def _detect_user_statistical_anomalies(
        self, 
        user_id: str, 
        events: List[Dict[str, Any]]
    ) -> List[SecurityAnomaly]:
        """Detect statistical anomalies for a specific user"""
        anomalies = []
        
        # Get baseline statistics
        baseline = await self._get_baseline_data(f"user_stats:{user_id}")
        
        if not baseline or baseline.get('sample_count', 0) < self.config.min_baseline_samples:
            # Not enough baseline data, build it from historical data
            baseline = await self._build_user_baseline(user_id)
            if not baseline:
                return anomalies  # Can't detect anomalies without baseline
        
        # Current session metrics
        current_metrics = self._calculate_session_metrics(events)
        
        # Check each metric against baseline
        for metric, current_value in current_metrics.items():
            if metric not in baseline:
                continue
            
            baseline_mean = baseline[metric]['mean']
            baseline_std = baseline[metric]['std']
            
            if baseline_std == 0:
                continue  # Can't compute z-score with zero std
            
            # Calculate z-score
            z_score = abs((current_value - baseline_mean) / baseline_std)
            
            if z_score > self.config.statistical_threshold:
                anomaly_score = min(1.0, z_score / (self.config.statistical_threshold * 2))
                
                # Determine severity based on z-score
                if z_score > 4.0:
                    severity = AnomalySeverity.CRITICAL
                elif z_score > 3.0:
                    severity = AnomalySeverity.HIGH
                elif z_score > 2.0:
                    severity = AnomalySeverity.MEDIUM
                else:
                    severity = AnomalySeverity.LOW
                
                anomaly = SecurityAnomaly(
                    anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                    severity=severity,
                    score=anomaly_score,
                    user_id=user_id,
                    description=f"Statistical outlier detected for {metric}",
                    evidence={
                        'metric': metric,
                        'current_value': current_value,
                        'z_score': z_score
                    },
                    baseline_data={
                        'mean': baseline_mean,
                        'std': baseline_std,
                        'sample_count': baseline[metric].get('sample_count', 0)
                    },
                    current_data={'value': current_value, 'events_count': len(events)},
                    detection_model=self.model_name,
                    confidence=min(1.0, z_score / 5.0)
                )
                
                anomalies.append(anomaly)
        
        return anomalies
    
    def _calculate_session_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate metrics for current session"""
        if not events:
            return {}
        
        metrics = {}
        
        # Event count
        metrics['event_count'] = len(events)
        
        # Time span
        timestamps = [datetime.fromisoformat(e['timestamp']) for e in events if e.get('timestamp')]
        if timestamps:
            time_span = (max(timestamps) - min(timestamps)).total_seconds()
            metrics['session_duration'] = time_span
            metrics['events_per_minute'] = len(events) / max(1, time_span / 60)
        
        # Event type distribution
        event_types = [e.get('event_type') for e in events]
        type_counts = {}
        for event_type in event_types:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        # Calculate entropy of event types (measure of randomness)
        total = len(events)
        entropy = 0
        for count in type_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        metrics['event_type_entropy'] = entropy
        
        # Error rate
        error_events = len([e for e in events if 'failure' in e.get('event_type', '').lower()])
        metrics['error_rate'] = error_events / len(events)
        
        # Unique endpoints accessed
        endpoints = set(e.get('endpoint', '') for e in events if e.get('endpoint'))
        metrics['unique_endpoints'] = len(endpoints)
        
        return metrics
    
    async def _build_user_baseline(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Build baseline statistics for a user from historical data"""
        # In a real implementation, this would query historical events
        # For now, return mock baseline
        
        # This would typically:
        # 1. Query events for the user over the baseline window
        # 2. Calculate statistics for various metrics
        # 3. Store the baseline for future use
        
        baseline = {
            'event_count': {'mean': 50.0, 'std': 15.0, 'sample_count': 30},
            'session_duration': {'mean': 1800.0, 'std': 600.0, 'sample_count': 30},
            'events_per_minute': {'mean': 2.5, 'std': 1.0, 'sample_count': 30},
            'event_type_entropy': {'mean': 2.0, 'std': 0.5, 'sample_count': 30},
            'error_rate': {'mean': 0.05, 'std': 0.02, 'sample_count': 30},
            'unique_endpoints': {'mean': 8.0, 'std': 3.0, 'sample_count': 30}
        }
        
        # Store baseline
        await self._set_baseline_data(f"user_stats:{user_id}", baseline)
        
        return baseline


class BehavioralAnomalyDetector(BaseAnomalyDetector):
    """Detects changes in user behavioral patterns"""
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]], 
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """Detect behavioral anomalies"""
        anomalies = []
        
        # Group events by user
        user_events = defaultdict(list)
        for event in events:
            if event.get('user_id'):
                user_events[event['user_id']].append(event)
        
        for user_id, user_event_list in user_events.items():
            user_anomalies = await self._detect_user_behavioral_anomalies(user_id, user_event_list)
            anomalies.extend(user_anomalies)
        
        return anomalies
    
    async def _detect_user_behavioral_anomalies(
        self, 
        user_id: str, 
        events: List[Dict[str, Any]]
    ) -> List[SecurityAnomaly]:
        """Detect behavioral anomalies for a user"""
        anomalies = []
        
        # Get behavioral baseline
        baseline = await self._get_baseline_data(f"user_behavior:{user_id}")
        
        if not baseline:
            baseline = await self._build_behavioral_baseline(user_id)
            if not baseline:
                return anomalies
        
        # Calculate current behavioral vector
        current_vector = self._calculate_behavioral_vector(events)
        baseline_vector = baseline.get('behavioral_vector', {})
        
        # Calculate behavioral similarity
        similarity = self._calculate_cosine_similarity(current_vector, baseline_vector)
        
        if similarity < self.config.behavioral_change_threshold:
            anomaly_score = 1.0 - similarity
            
            # Determine severity
            if similarity < 0.3:
                severity = AnomalySeverity.CRITICAL
            elif similarity < 0.5:
                severity = AnomalySeverity.HIGH
            elif similarity < 0.7:
                severity = AnomalySeverity.MEDIUM
            else:
                severity = AnomalySeverity.LOW
            
            anomaly = SecurityAnomaly(
                anomaly_type=AnomalyType.BEHAVIORAL_CHANGE,
                severity=severity,
                score=anomaly_score,
                user_id=user_id,
                description=f"Behavioral pattern deviation detected (similarity: {similarity:.3f})",
                evidence={
                    'behavioral_similarity': similarity,
                    'deviation_score': 1.0 - similarity
                },
                baseline_data=baseline_vector,
                current_data=current_vector,
                detection_model=self.model_name,
                confidence=anomaly_score
            )
            
            anomalies.append(anomaly)
        
        return anomalies
    
    def _calculate_behavioral_vector(self, events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate behavioral feature vector from events"""
        if not events:
            return {}
        
        vector = {}
        
        # Time-based features
        timestamps = [datetime.fromisoformat(e['timestamp']) for e in events if e.get('timestamp')]
        if timestamps:
            hours = [t.hour for t in timestamps]
            vector['avg_hour'] = statistics.mean(hours)
            vector['hour_std'] = statistics.stdev(hours) if len(hours) > 1 else 0
            
            # Day of week distribution
            weekdays = [t.weekday() for t in timestamps]
            vector['avg_weekday'] = statistics.mean(weekdays)
        
        # Endpoint usage pattern
        endpoints = [e.get('endpoint', '') for e in events if e.get('endpoint')]
        endpoint_counts = {}
        for endpoint in endpoints:
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
        
        # Top endpoint usage ratios
        if endpoint_counts:
            sorted_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)
            total_requests = sum(endpoint_counts.values())
            
            for i, (endpoint, count) in enumerate(sorted_endpoints[:5]):
                vector[f'top_endpoint_{i}_ratio'] = count / total_requests
        
        # Request method distribution
        methods = [e.get('method', '') for e in events if e.get('method')]
        method_counts = {}
        for method in methods:
            method_counts[method] = method_counts.get(method, 0) + 1
        
        if method_counts:
            total_methods = sum(method_counts.values())
            for method, count in method_counts.items():
                vector[f'method_{method.lower()}_ratio'] = count / total_methods
        
        # Event type patterns
        event_types = [e.get('event_type', '') for e in events]
        type_counts = {}
        for event_type in event_types:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        if type_counts:
            total_events = len(events)
            for event_type, count in type_counts.items():
                vector[f'event_{event_type}_ratio'] = count / total_events
        
        return vector
    
    def _calculate_cosine_similarity(
        self, 
        vector1: Dict[str, float], 
        vector2: Dict[str, float]
    ) -> float:
        """Calculate cosine similarity between two feature vectors"""
        
        # Get common keys
        common_keys = set(vector1.keys()) & set(vector2.keys())
        
        if not common_keys:
            return 0.0
        
        # Calculate dot product and magnitudes
        dot_product = sum(vector1[key] * vector2[key] for key in common_keys)
        magnitude1 = math.sqrt(sum(vector1[key]**2 for key in common_keys))
        magnitude2 = math.sqrt(sum(vector2[key]**2 for key in common_keys))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _build_behavioral_baseline(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Build behavioral baseline for a user"""
        # Mock implementation - in reality would analyze historical data
        
        baseline = {
            'behavioral_vector': {
                'avg_hour': 14.0,  # 2 PM average
                'hour_std': 3.0,
                'avg_weekday': 2.0,  # Tuesday average
                'top_endpoint_0_ratio': 0.4,
                'top_endpoint_1_ratio': 0.25,
                'method_get_ratio': 0.7,
                'method_post_ratio': 0.3,
                'event_data_access_ratio': 0.6,
                'event_auth_success_ratio': 0.1
            },
            'sample_count': 100,
            'last_updated': datetime.now().isoformat()
        }
        
        await self._set_baseline_data(f"user_behavior:{user_id}", baseline)
        return baseline


class TemporalAnomalyDetector(BaseAnomalyDetector):
    """Detects temporal anomalies (unusual timing patterns)"""
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]], 
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """Detect temporal anomalies"""
        anomalies = []
        
        for event in events:
            timestamp_str = event.get('timestamp')
            if not timestamp_str:
                continue
                
            timestamp = datetime.fromisoformat(timestamp_str)
            user_id = event.get('user_id')
            
            # Check for off-hours activity
            if self._is_off_hours(timestamp):
                anomaly = SecurityAnomaly(
                    anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                    severity=AnomalySeverity.MEDIUM,
                    score=0.6,
                    user_id=user_id,
                    timestamp=timestamp,
                    description=f"Off-hours activity detected at {timestamp.strftime('%H:%M:%S')}",
                    evidence={
                        'hour': timestamp.hour,
                        'is_weekend': timestamp.weekday() >= 5,
                        'normal_hours': f"{self.config.normal_hours_start}-{self.config.normal_hours_end}"
                    },
                    detection_model=self.model_name,
                    confidence=0.7
                )
                anomalies.append(anomaly)
            
            # Check for weekend activity (if user typically doesn't work weekends)
            if timestamp.weekday() >= 5:  # Saturday or Sunday
                # This would typically check against user's baseline
                anomaly_score = 0.4 * self.config.weekend_penalty_factor
                if anomaly_score > 0.5:
                    anomaly = SecurityAnomaly(
                        anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                        severity=AnomalySeverity.LOW,
                        score=min(1.0, anomaly_score),
                        user_id=user_id,
                        timestamp=timestamp,
                        description=f"Weekend activity detected",
                        evidence={
                            'weekday': timestamp.weekday(),
                            'is_weekend': True
                        },
                        detection_model=self.model_name,
                        confidence=0.5
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _is_off_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is outside normal business hours"""
        hour = timestamp.hour
        return hour < self.config.normal_hours_start or hour > self.config.normal_hours_end


class VelocityAnomalyDetector(BaseAnomalyDetector):
    """Detects impossible travel velocities between locations"""
    
    def __init__(self, config: DetectionConfig, redis_client: Optional[aioredis.Redis] = None):
        super().__init__(config, redis_client)
        self.location_cache = {}  # IP -> (lat, lon, timestamp)
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]], 
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """Detect velocity anomalies"""
        anomalies = []
        
        # Group events by user and sort by timestamp
        user_events = defaultdict(list)
        for event in events:
            if event.get('user_id') and event.get('ip_address'):
                user_events[event['user_id']].append(event)
        
        for user_id, user_event_list in user_events.items():
            # Sort events by timestamp
            sorted_events = sorted(
                user_event_list, 
                key=lambda x: datetime.fromisoformat(x['timestamp'])
            )
            
            velocity_anomalies = await self._detect_velocity_anomalies(user_id, sorted_events)
            anomalies.extend(velocity_anomalies)
        
        return anomalies
    
    async def _detect_velocity_anomalies(
        self, 
        user_id: str, 
        events: List[Dict[str, Any]]
    ) -> List[SecurityAnomaly]:
        """Detect impossible travel velocities for a user"""
        anomalies = []
        
        if len(events) < 2:
            return anomalies
        
        previous_event = None
        
        for event in events:
            ip_address = event.get('ip_address')
            timestamp = datetime.fromisoformat(event['timestamp'])
            
            # Get geolocation for IP (mock implementation)
            location = await self._get_ip_geolocation(ip_address)
            
            if previous_event and location:
                prev_ip = previous_event.get('ip_address')
                prev_timestamp = datetime.fromisoformat(previous_event['timestamp'])
                prev_location = await self._get_ip_geolocation(prev_ip)
                
                if prev_location and location != prev_location:
                    # Calculate distance and time
                    distance_km = self._calculate_distance(prev_location, location)
                    time_hours = (timestamp - prev_timestamp).total_seconds() / 3600
                    
                    if time_hours > 0:
                        velocity_kmh = distance_km / time_hours
                        
                        if velocity_kmh > self.config.velocity_threshold_kmh:
                            anomaly_score = min(1.0, velocity_kmh / (self.config.velocity_threshold_kmh * 2))
                            
                            anomaly = SecurityAnomaly(
                                anomaly_type=AnomalyType.VELOCITY_ANOMALY,
                                severity=AnomalySeverity.HIGH if velocity_kmh > 2000 else AnomalySeverity.MEDIUM,
                                score=anomaly_score,
                                user_id=user_id,
                                ip_address=ip_address,
                                timestamp=timestamp,
                                description=f"Impossible travel velocity detected: {velocity_kmh:.1f} km/h",
                                evidence={
                                    'previous_ip': prev_ip,
                                    'current_ip': ip_address,
                                    'distance_km': distance_km,
                                    'time_hours': time_hours,
                                    'velocity_kmh': velocity_kmh,
                                    'threshold_kmh': self.config.velocity_threshold_kmh
                                },
                                baseline_data={
                                    'previous_location': prev_location,
                                    'previous_timestamp': prev_timestamp.isoformat()
                                },
                                current_data={
                                    'current_location': location,
                                    'current_timestamp': timestamp.isoformat()
                                },
                                detection_model=self.model_name,
                                confidence=min(1.0, anomaly_score * 1.5)
                            )
                            
                            anomalies.append(anomaly)
            
            previous_event = event
        
        return anomalies
    
    async def _get_ip_geolocation(self, ip_address: str) -> Optional[Tuple[float, float]]:
        """Get geolocation for IP address (mock implementation)"""
        # In real implementation, this would use a geolocation service
        # like MaxMind GeoIP2, IPinfo, etc.
        
        # Mock data for testing
        mock_locations = {
            '192.168.1.1': (37.7749, -122.4194),  # San Francisco
            '10.0.0.1': (40.7128, -74.0060),      # New York
            '172.16.0.1': (51.5074, -0.1278),     # London
            '203.0.113.1': (35.6762, 139.6503),   # Tokyo
        }
        
        return mock_locations.get(ip_address)
    
    def _calculate_distance(
        self, 
        location1: Tuple[float, float], 
        location2: Tuple[float, float]
    ) -> float:
        """Calculate distance between two geographic points using Haversine formula"""
        lat1, lon1 = location1
        lat2, lon2 = location2
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        earth_radius_km = 6371
        
        return earth_radius_km * c


class AnomalyDetector:
    """
    Main anomaly detection coordinator that runs multiple detection algorithms.
    """
    
    def __init__(self, config: DetectionConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        
        # Initialize detectors
        self.detectors = []
        if config.enable_detection:
            self.detectors = [
                StatisticalAnomalyDetector(config, redis_client),
                BehavioralAnomalyDetector(config, redis_client),
                TemporalAnomalyDetector(config, redis_client),
                VelocityAnomalyDetector(config, redis_client),
            ]
        
        # Anomaly history for correlation
        self.anomaly_history = deque(maxlen=1000)
    
    async def detect_anomalies(
        self, 
        events: List[Dict[str, Any]],
        context: Dict[str, Any] = None
    ) -> List[SecurityAnomaly]:
        """
        Run anomaly detection across all algorithms.
        
        Args:
            events: List of security events to analyze
            context: Additional context for detection
            
        Returns:
            List of detected anomalies
        """
        if not self.config.enable_detection or not events:
            return []
        
        all_anomalies = []
        
        # Run each detector
        for detector in self.detectors:
            try:
                detector_anomalies = await detector.detect_anomalies(events, context)
                all_anomalies.extend(detector_anomalies)
                logger.debug(f"{detector.model_name} detected {len(detector_anomalies)} anomalies")
            except Exception as e:
                logger.error(f"Error in {detector.model_name}: {e}")
        
        # Deduplicate and consolidate similar anomalies
        consolidated_anomalies = self._consolidate_anomalies(all_anomalies)
        
        # Update anomaly history
        for anomaly in consolidated_anomalies:
            self.anomaly_history.append(anomaly.to_dict())
        
        # Filter by score threshold
        significant_anomalies = [
            anomaly for anomaly in consolidated_anomalies
            if anomaly.score >= self.config.alert_score_threshold
        ]
        
        logger.info(f"Detected {len(significant_anomalies)} significant anomalies out of {len(consolidated_anomalies)} total")
        
        return significant_anomalies
    
    def _consolidate_anomalies(self, anomalies: List[SecurityAnomaly]) -> List[SecurityAnomaly]:
        """Consolidate similar anomalies to reduce noise"""
        if not anomalies:
            return []
        
        # Group by user and timestamp (within 5 minutes)
        consolidated = []
        used_indices = set()
        
        for i, anomaly1 in enumerate(anomalies):
            if i in used_indices:
                continue
            
            similar_anomalies = [anomaly1]
            used_indices.add(i)
            
            for j, anomaly2 in enumerate(anomalies[i+1:], i+1):
                if j in used_indices:
                    continue
                
                if self._are_similar_anomalies(anomaly1, anomaly2):
                    similar_anomalies.append(anomaly2)
                    used_indices.add(j)
            
            # Create consolidated anomaly
            if len(similar_anomalies) > 1:
                consolidated_anomaly = self._merge_anomalies(similar_anomalies)
                consolidated.append(consolidated_anomaly)
            else:
                consolidated.append(anomaly1)
        
        return consolidated
    
    def _are_similar_anomalies(self, anomaly1: SecurityAnomaly, anomaly2: SecurityAnomaly) -> bool:
        """Check if two anomalies are similar enough to consolidate"""
        
        # Same user and within 5 minutes
        if (anomaly1.user_id == anomaly2.user_id and
            abs((anomaly1.timestamp - anomaly2.timestamp).total_seconds()) <= 300):
            return True
        
        # Same IP and similar type
        if (anomaly1.ip_address == anomaly2.ip_address and
            anomaly1.anomaly_type == anomaly2.anomaly_type):
            return True
        
        return False
    
    def _merge_anomalies(self, anomalies: List[SecurityAnomaly]) -> SecurityAnomaly:
        """Merge multiple similar anomalies into one"""
        
        # Use the highest severity and score
        max_severity = max(anomalies, key=lambda x: ['low', 'medium', 'high', 'critical'].index(x.severity.value))
        max_score_anomaly = max(anomalies, key=lambda x: x.score)
        
        # Combine descriptions
        descriptions = [a.description for a in anomalies]
        combined_description = f"Multiple anomalies detected: {'; '.join(set(descriptions))}"
        
        # Merge evidence
        combined_evidence = {}
        for anomaly in anomalies:
            combined_evidence.update(anomaly.evidence)
        combined_evidence['anomaly_count'] = len(anomalies)
        combined_evidence['detection_models'] = list(set(a.detection_model for a in anomalies))
        
        return SecurityAnomaly(
            anomaly_type=max_score_anomaly.anomaly_type,
            severity=max_severity.severity,
            score=max_score_anomaly.score,
            timestamp=min(anomalies, key=lambda x: x.timestamp).timestamp,
            user_id=max_score_anomaly.user_id,
            ip_address=max_score_anomaly.ip_address,
            description=combined_description,
            evidence=combined_evidence,
            detection_model="Consolidated",
            confidence=statistics.mean(a.confidence for a in anomalies)
        )
    
    async def get_anomaly_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of anomalies in the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_anomalies = [
            anomaly for anomaly in self.anomaly_history
            if datetime.fromisoformat(anomaly['timestamp']) > cutoff_time
        ]
        
        if not recent_anomalies:
            return {
                'total_anomalies': 0,
                'time_period_hours': hours,
                'summary': {}
            }
        
        # Analyze anomalies
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        by_user = defaultdict(int)
        
        for anomaly in recent_anomalies:
            by_type[anomaly['anomaly_type']] += 1
            by_severity[anomaly['severity']] += 1
            if anomaly.get('user_id'):
                by_user[anomaly['user_id']] += 1
        
        return {
            'total_anomalies': len(recent_anomalies),
            'time_period_hours': hours,
            'summary': {
                'by_type': dict(by_type),
                'by_severity': dict(by_severity),
                'top_users': dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            'high_risk_indicators': self._identify_high_risk_patterns(recent_anomalies)
        }
    
    def _identify_high_risk_patterns(self, anomalies: List[Dict[str, Any]]) -> List[str]:
        """Identify high-risk patterns in anomalies"""
        indicators = []
        
        # Count critical/high severity anomalies
        high_risk_count = sum(1 for a in anomalies if a['severity'] in ['high', 'critical'])
        if high_risk_count > 5:
            indicators.append(f"High number of critical/high severity anomalies: {high_risk_count}")
        
        # Check for repeated users
        user_counts = defaultdict(int)
        for anomaly in anomalies:
            if anomaly.get('user_id'):
                user_counts[anomaly['user_id']] += 1
        
        frequent_users = [user for user, count in user_counts.items() if count >= 3]
        if frequent_users:
            indicators.append(f"Users with multiple anomalies: {', '.join(frequent_users[:5])}")
        
        # Check for velocity anomalies
        velocity_anomalies = [a for a in anomalies if a['anomaly_type'] == 'velocity_anomaly']
        if velocity_anomalies:
            indicators.append(f"Impossible travel detected for {len(velocity_anomalies)} events")
        
        return indicators
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for anomaly detection system"""
        return {
            'detection_enabled': self.config.enable_detection,
            'active_detectors': len(self.detectors),
            'detector_types': [d.model_name for d in self.detectors],
            'anomaly_history_size': len(self.anomaly_history),
            'redis_connected': bool(self.redis_client),
            'timestamp': time.time()
        }
#!/usr/bin/env python3

class ConditionAnalyzer:
    """
    Analyzes condition structure once and caches the analysis for efficient evaluation.
    Provides modular functions for different analysis tasks.
    """

    def __init__(self, condition):
        self.condition = condition
        self.analysis = self._analyze_condition_structure()

    def _analyze_condition_structure(self):
        return {
            'has_live_data': self._check_has_live_data(self.condition),
            'live_data_conditions': self._extract_live_data_conditions(self.condition),
            'non_live_data_conditions': self._extract_non_live_data_conditions(self.condition),
            'evaluation_structure': self._build_evaluation_structure(self.condition),
            'group_logic': self._extract_group_logic(self.condition)
        }

    def _check_has_live_data(self, condition):
        if self._is_group_condition(condition):
            return any(self._check_has_live_data(sub) for sub in condition['conditions'])
        return self._is_live_data_condition(condition)

    def _extract_live_data_conditions(self, condition):
        out = []
        if self._is_group_condition(condition):
            for sub in condition['conditions']:
                out.extend(self._extract_live_data_conditions(sub))
        elif self._is_live_data_condition(condition):
            out.append(condition)
        return out

    def _extract_non_live_data_conditions(self, condition):
        out = []
        if self._is_group_condition(condition):
            for sub in condition['conditions']:
                out.extend(self._extract_non_live_data_conditions(sub))
        elif not self._is_live_data_condition(condition):
            out.append(condition)
        return out

    def _build_evaluation_structure(self, condition):
        if self._is_group_condition(condition):
            return {
                'type': 'group',
                'logic': condition.get('groupLogic', 'AND'),
                'conditions': [self._build_evaluation_structure(sub) for sub in condition['conditions']]
            }
        return {
            'type': 'condition',
            'condition': condition,
            'requires_ticks': self._is_live_data_condition(condition)
        }

    def _extract_group_logic(self, condition):
        if self._is_group_condition(condition):
            return condition.get('groupLogic', 'AND')
        return None

    def _is_group_condition(self, condition):
        return isinstance(condition, dict) and 'groupLogic' in condition

    def _is_live_data_condition(self, condition):
        if not isinstance(condition, dict):
            return False
        if 'lhs' in condition and isinstance(condition['lhs'], dict):
            if self._contains_live_data(condition['lhs']):
                return True
        if 'rhs' in condition and isinstance(condition['rhs'], dict):
            if self._contains_live_data(condition['rhs']):
                return True
        return False

    def _contains_live_data(self, expression):
        if not isinstance(expression, dict):
            return False
        if expression.get('type') == 'live_data':
            return True
        for _, value in expression.items():
            if isinstance(value, dict) and self._contains_live_data(value):
                return True
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and self._contains_live_data(item):
                        return True
        return False

    def get_analysis_summary(self):
        return {
            'has_live_data': self.analysis['has_live_data'],
            'live_data_count': len(self.analysis['live_data_conditions']),
            'non_live_data_count': len(self.analysis['non_live_data_conditions']),
            'group_logic': self.analysis['group_logic'],
            'total_conditions': (len(self.analysis['live_data_conditions']) + len(self.analysis['non_live_data_conditions']))
        }

    def should_use_stage2(self):
        return self.analysis['has_live_data']

    def get_live_data_conditions(self):
        return self.analysis['live_data_conditions']

    def get_non_live_data_conditions(self):
        return self.analysis['non_live_data_conditions']

    def get_evaluation_structure(self):
        return self.analysis['evaluation_structure']



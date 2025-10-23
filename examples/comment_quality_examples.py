#!/usr/bin/env python3
"""
Comment Quality Assessment Examples

This script demonstrates how to use the new comment quality assessment feature
in AppenCorrect to evaluate comment quality in the context of rating tasks.

The feature evaluates comments based on:
- Technical quality (grammar, spelling, formatting)
- Content quality (clarity, relevance, completeness)
- Length appropriateness 
- Rating task suitability

Usage:
    python comment_quality_examples.py
"""

import os
import sys
import json
from typing import List, Dict, Any

# Add parent directory to path to import appencorrect
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appencorrect import PythonAPI

def print_quality_assessment(result: Dict[str, Any], comment_description: str = ""):
    """Pretty print quality assessment results."""
    print(f"\n{'='*60}")
    if comment_description:
        print(f"Assessment for: {comment_description}")
    print(f"{'='*60}")
    
    if result['status'] != 'success':
        print(f"❌ Error: {result.get('message', 'Unknown error')}")
        return
    
    # Main quality metrics
    score = result['quality_score']
    level = result['quality_level']
    print(f"🎯 Overall Quality Score: {score}/10 ({level.title()})")
    
    # Quality level emoji
    level_emojis = {
        'excellent': '🌟',
        'good': '👍', 
        'fair': '⚠️',
        'poor': '❌'
    }
    emoji = level_emojis.get(level, '❓')
    print(f"{emoji} Quality Level: {level.title()}")
    
    # Assessment summary
    print(f"\n📝 Assessment:")
    print(f"   {result['assessment']}")
    
    # Factor breakdown
    factors = result.get('factors', {})
    if factors:
        print(f"\n📊 Factor Breakdown:")
        for factor_name, factor_data in factors.items():
            factor_score = factor_data.get('score', 'N/A')
            factor_notes = factor_data.get('notes', 'No notes')
            print(f"   • {factor_name.replace('_', ' ').title()}: {factor_score}/10")
            print(f"     {factor_notes}")
    
    # Strengths
    strengths = result.get('strengths', [])
    if strengths:
        print(f"\n✅ Strengths:")
        for strength in strengths:
            print(f"   • {strength}")
    
    # Suggestions for improvement
    suggestions = result.get('suggestions', [])
    if suggestions:
        print(f"\n💡 Suggestions for Improvement:")
        for suggestion in suggestions:
            print(f"   • {suggestion}")
    
    # Technical analysis
    analysis = result.get('comment_analysis', {})
    if analysis:
        print(f"\n📈 Technical Analysis:")
        word_count = analysis.get('word_count', 0)
        sentence_count = analysis.get('sentence_count', 0)
        error_count = analysis.get('error_count', 0)
        char_count = analysis.get('character_count', 0)
        
        print(f"   • Word count: {word_count}")
        print(f"   • Sentence count: {sentence_count}")
        print(f"   • Grammar/spelling errors: {error_count}")
        
        # Highlight character count with length requirements
        if char_count < 100:
            print(f"   • Character count: {char_count} 🚨 (Under 100 - max score 4/10)")
        elif char_count < 300:
            print(f"   • Character count: {char_count} ⚠️ (Under 300 - cannot reach 9-10/10)")
        else:
            print(f"   • Character count: {char_count} ✅ (300+ - can achieve excellent)")
        
        # Check if length penalty was applied
        assessment = result.get('assessment', '')
        if 'Length-adjusted' in assessment:
            penalty_info = assessment.split('[Length-adjusted:')[1].split(']')[0]
            print(f"   • Length penalty: {penalty_info.strip()}")
    
    # Technical corrections found
    corrections = result.get('technical_corrections', [])
    if corrections:
        print(f"\n🔧 Technical Corrections Found:")
        for correction in corrections[:3]:  # Show first 3 corrections
            original = correction.get('original', '')
            suggestion = correction.get('suggestion', '')
            corr_type = correction.get('type', 'unknown')
            print(f"   • {corr_type.title()}: '{original}' → '{suggestion}'")
        if len(corrections) > 3:
            print(f"   • ... and {len(corrections) - 3} more")


def main():
    """Run comment quality assessment examples."""
    print("🎯 AppenCorrect Comment Quality Assessment Examples")
    print("=" * 60)
    
    # Initialize the API
    try:
        api = PythonAPI()
        print("✅ AppenCorrect Python API initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize API: {e}")
        print("Please ensure you have set your GEMINI_API_KEY environment variable")
        return
    
    # Test cases with different quality levels and lengths
    test_cases = [
        {
            "comment": "This product demonstrates exceptional build quality with meticulous attention to detail that consistently exceeds expectations. The materials feel genuinely premium and remarkably durable, while the innovative design strikes an excellent balance between functionality and aesthetic appeal. I would highly recommend this to anyone seeking a reliable, expertly-crafted solution that provides outstanding long-term value for the investment.",
            "context": "Product review rating task",
            "description": "High-quality detailed review (300+ characters)"
        },
        {
            "comment": "This product has good build quality and works as expected. The design is functional and the materials seem durable. I would recommend it for basic use cases and the price point is reasonable for what you get.",
            "context": "Product review rating task", 
            "description": "Medium-length comment with good content (200+ characters)"
        },
        {
            "comment": "This product is really good and I like it alot. It works fine and does what its supposed to do. Would recomend.",
            "context": "Product review rating task", 
            "description": "Short comment with spelling/grammar errors (~120 characters)"
        },
        {
            "comment": "Good product!",
            "context": "Product review rating task",
            "description": "Very brief comment - insufficient for rating tasks (13 characters)"
        },
        {
            "comment": "Bad quality.",
            "context": "Product review rating task",
            "description": "Another very brief comment lacking explanation (12 characters)"
        },
        {
            "comment": "The theoretical framework underlying this solution demonstrates significant conceptual sophistication while maintaining practical applicability across diverse implementation scenarios, though the documentation could benefit from more concrete examples.",
            "context": "Academic paper rating task",
            "description": "Academic-style assessment with sufficient detail (250+ characters)"
        }
    ]
    
    # Run assessments
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}/{len(test_cases)}")
        
        try:
            result = api.assess_comment_quality(
                comment=test_case["comment"],
                rating_context=test_case["context"]
            )
            
            print_quality_assessment(result, test_case["description"])
            
        except Exception as e:
            print(f"❌ Error processing test case {i}: {e}")
    
    print(f"\n{'='*60}")
    print("🎯 Comment Quality Assessment Examples Complete")
    print("\n💡 Usage Tips:")
    print("   • Use rating_context to provide task-specific context")
    print("   • Quality scores range from 1-10 (10 being highest)")
    print("   • The feature considers technical accuracy AND content quality")
    print("   • Suggestions help improve comment quality for rating tasks")
    print("\n📚 API Usage:")
    print("   result = api.assess_comment_quality(comment, rating_context)")
    print("   print(f\"Score: {result['quality_score']}/10\")")


if __name__ == "__main__":
    main() 
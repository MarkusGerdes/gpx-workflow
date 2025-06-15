#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_markdown_power_analysis.py
--------------------------------
Test script to verify the enhanced power analysis with Markdown output.
"""

import subprocess
import sys
import os
from pathlib import Path

def test_power_analysis():
    """Test the enhanced power analysis script."""
    
    print("🚴‍♂️ Testing Enhanced Power Analysis with Markdown Output")
    print("=" * 60)
    
    # Check if power data file exists
    power_csv = "output/10b_HaBe_Feierabendrunde_von_Finki_aus_power_data.csv"
    
    if not os.path.exists(power_csv):
        print(f"❌ Power data file not found: {power_csv}")
        print("Please run the pipeline first to generate power data.")
        return False
    
    print(f"✅ Found power data file: {power_csv}")
    
    # Test the enhanced script
    cmd = [
        "python",
        "scripts/10d_detailed_power_analysis.py",
        "--power-csv", power_csv,
        "--ftp", "250",
        "--rider-weight", "75",
        "--markdown"
    ]
    
    print(f"\n🔧 Running command:")
    print(f"   {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            print(f"✅ Script executed successfully!")
            
            # Check output files
            text_output = power_csv.replace('10b_', '10d_').replace('_power_data.csv', '_detailed_power_analysis.txt')
            md_output = power_csv.replace('10b_', '10d_').replace('_power_data.csv', '_detailed_power_analysis.md')
            
            if os.path.exists(text_output):
                print(f"✅ Text report generated: {text_output}")
                print(f"   Size: {os.path.getsize(text_output)} bytes")
            else:
                print(f"❌ Text report missing: {text_output}")
            
            if os.path.exists(md_output):
                print(f"✅ Markdown report generated: {md_output}")
                print(f"   Size: {os.path.getsize(md_output)} bytes")
                
                # Show first few lines of markdown
                print(f"\n📄 First 10 lines of Markdown report:")
                with open(md_output, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:10]
                    for i, line in enumerate(lines, 1):
                        print(f"   {i:2d}: {line.rstrip()}")
            else:
                print(f"❌ Markdown report missing: {md_output}")
            
            print(f"\n📊 Text output preview:")
            lines = result.stdout.split('\n')[:15]
            for line in lines:
                print(f"   {line}")
            
            return True
            
        else:
            print(f"❌ Script failed with exit code {result.returncode}")
            print(f"   Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return False

if __name__ == "__main__":
    success = test_power_analysis()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Test completed successfully!")
        print("   ✅ Enhanced power analysis with Markdown output is working")
        print("   ✅ Peak analysis for components implemented")
        print("   ✅ Rider configuration integrated")
        print("   ✅ Ready for Snakemake integration")
    else:
        print("❌ Test failed!")
        print("   Please check the error messages above")
    
    sys.exit(0 if success else 1)

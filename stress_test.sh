#!/bin/bash
# AppenCorrect 500-Connection Stress Test
# Generates diverse sentences with errors to test system performance

API_KEY="appencorrect_6cc586912e264062afdc0810f22d075a"
NUM_REQUESTS=${1:-500}
BATCH_SIZE=${2:-50}
URL="https://appencorrect.xlostxcoz.com/check"

echo "🧪 AppenCorrect Stress Test"
echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
echo "🎯 Target: $NUM_REQUESTS requests in batches of $BATCH_SIZE"
echo "=" | tr ' ' '=' | head -c 80
echo

# Sentence components with errors
adjectives=("beautifull" "wonderfull" "amasing" "incredibel" "fantastc" "awsome" "excelent" "perfet")
nouns=("sentance" "documant" "analiysis" "performanc" "sistem" "machien" "proccess" "requirment")
verbs=("proces" "analiz" "determin" "evaluat" "demonstrat" "implament" "optmize" "achiev")
adverbs=("efficently" "accuratly" "consistantly" "immediatly" "automaticaly" "sucessfully" "definitly" "completly")
locations=("databas" "servr" "memori" "cach" "netwrk" "sistem" "platfrom" "environmnt")

templates=(
    "The ADJECTIVE NOUN VERB ADVERB through the LOCATION."
    "What is the ADJECTIVE NOUN that VERB in LOCATION?"
    "This NOUN has many ADJECTIVE errors that need correction."
    "The ADJECTIVE NOUN VERB ADVERB when processing."
    "How can we VERB the ADJECTIVE NOUN more ADVERB?"
    "The NOUN was ADJECTIVE and efficient during testing."
    "I think the NOUN will VERB ADVERB in the LOCATION."
    "What kind of ADJECTIVE errors VERB ADVERB?"
    "The ADJECTIVE NOUN VERB because it was necessary."
    "This comprehensive NOUN VERB ADVERB with errors."
)

generate_sentence() {
    local template=${templates[$((RANDOM % ${#templates[@]}))]}
    local adj=${adjectives[$((RANDOM % ${#adjectives[@]}))]}
    local noun=${nouns[$((RANDOM % ${#nouns[@]}))]}
    local verb=${verbs[$((RANDOM % ${#verbs[@]}))]}
    local adv=${adverbs[$((RANDOM % ${#adverbs[@]}))]}
    local loc=${locations[$((RANDOM % ${#locations[@]}))]}
    
    # Replace placeholders
    sentence=$template
    sentence=${sentence//ADJECTIVE/$adj}
    sentence=${sentence//NOUN/$noun}
    sentence=${sentence//VERB/$verb}
    sentence=${sentence//ADVERB/$adv}
    sentence=${sentence//LOCATION/$loc}
    
    echo "$sentence"
}

# Statistics tracking
success_count=0
error_count=0
total_response_time=0
start_time=$(date +%s)

# Create temporary files
mkdir -p /tmp/stress_test_$$
result_file="/tmp/stress_test_$$/results.txt"
error_file="/tmp/stress_test_$$/errors.txt"

echo "📚 Generating $NUM_REQUESTS unique test sentences..."

# Run stress test in batches
for ((batch_start=1; batch_start<=NUM_REQUESTS; batch_start+=BATCH_SIZE)); do
    batch_end=$((batch_start + BATCH_SIZE - 1))
    if [ $batch_end -gt $NUM_REQUESTS ]; then
        batch_end=$NUM_REQUESTS
    fi
    
    batch_num=$(((batch_start - 1) / BATCH_SIZE + 1))
    total_batches=$(((NUM_REQUESTS + BATCH_SIZE - 1) / BATCH_SIZE))
    
    echo "🔄 Batch $batch_num/$total_batches: Processing requests $batch_start-$batch_end"
    
    # Launch batch of concurrent requests
    for ((i=batch_start; i<=batch_end; i++)); do
        {
            sentence=$(generate_sentence)
            
            response=$(curl -s -w "%{http_code}:%{time_total}" -X POST "$URL" \
                -H "Content-Type: application/json" \
                -H "X-API-Key: $API_KEY" \
                -d "{\"text\": \"Request $i: $sentence\", \"language\": \"english\"}" \
                2>/dev/null)
            
            # Parse response
            http_code=${response##*:}
            time_total=${response##*:}
            time_total=${time_total%:*}
            response_body=${response%:*}
            
            if [[ "$http_code" == "200" ]]; then
                corrections=$(echo "$response_body" | jq -r '.corrections | length' 2>/dev/null || echo "0")
                cached=$(echo "$response_body" | jq -r '.statistics.processing_time' 2>/dev/null | grep -q "^0\.0" && echo "cached" || echo "fresh")
                echo "✓$i:$time_total:$corrections:$cached" >> "$result_file"
            else
                echo "✗$i:$http_code:$time_total" >> "$error_file"
            fi
        } &
    done
    
    # Wait for batch to complete
    wait
    
    # Progress update
    echo -n "  "
    if [ -f "$result_file" ]; then
        batch_success=$(wc -l < "$result_file" 2>/dev/null || echo "0")
    else
        batch_success=0
    fi
    if [ -f "$error_file" ]; then
        batch_errors=$(wc -l < "$error_file" 2>/dev/null || echo "0")
    else
        batch_errors=0
    fi
    echo "Results: ${batch_success} success, ${batch_errors} errors"
done

# Final statistics
end_time=$(date +%s)
total_time=$((end_time - start_time))

if [ -f "$result_file" ]; then
    success_count=$(wc -l < "$result_file")
    cached_count=$(grep -c "cached" "$result_file" 2>/dev/null || echo "0")
    # Calculate total corrections
    total_corrections=$(awk -F: '{sum+=$3} END {print sum+0}' "$result_file" 2>/dev/null || echo "0")
else
    success_count=0
    cached_count=0
    total_corrections=0
fi

if [ -f "$error_file" ]; then
    error_count=$(wc -l < "$error_file")
else
    error_count=0
fi

echo
echo "=" | tr ' ' '=' | head -c 80
echo
echo "📊 FINAL STRESS TEST RESULTS"
echo "=" | tr ' ' '=' | head -c 80
echo
echo "📈 Request Statistics:"
echo "  Total Requests: $NUM_REQUESTS"
echo "  Successful: $success_count ($(echo "scale=1; $success_count * 100 / $NUM_REQUESTS" | bc)%)"
echo "  Failed: $error_count ($(echo "scale=1; $error_count * 100 / $NUM_REQUESTS" | bc)%)"
echo "  Cached Responses: $cached_count ($(echo "scale=1; $cached_count * 100 / $success_count" | bc 2>/dev/null || echo "0")%)"
echo
echo "⚡ Performance Metrics:"
echo "  Total Time: ${total_time}s"
echo "  Throughput: $(echo "scale=2; $NUM_REQUESTS / $total_time" | bc) requests/second"
echo "  Corrections Found: $total_corrections"
echo
echo "🎯 System Performance:"
if [ $success_count -ge $((NUM_REQUESTS * 99 / 100)) ]; then
    echo "  ✅ EXCELLENT: >99% success rate"
elif [ $success_count -ge $((NUM_REQUESTS * 95 / 100)) ]; then
    echo "  ✅ GOOD: >95% success rate"
elif [ $success_count -ge $((NUM_REQUESTS * 90 / 100)) ]; then
    echo "  ⚠️ ACCEPTABLE: >90% success rate"
else
    echo "  ❌ POOR: <90% success rate - investigation needed"
fi

throughput=$(echo "scale=0; $NUM_REQUESTS / $total_time" | bc)
if [ $throughput -ge 10 ]; then
    echo "  🚀 EXCELLENT: >10 req/sec throughput"
elif [ $throughput -ge 5 ]; then
    echo "  ✅ GOOD: >5 req/sec throughput"
else
    echo "  ⚠️ SLOW: <5 req/sec throughput"
fi

# Show sample errors if any
if [ $error_count -gt 0 ] && [ -f "$error_file" ]; then
    echo
    echo "🔍 Sample Errors (first 5):"
    head -5 "$error_file" | while IFS=: read -r req_id error_code time_total; do
        echo "  Request $req_id: HTTP $error_code (${time_total}s)"
    done
fi

# Cleanup
rm -rf "/tmp/stress_test_$$"

echo
echo "✅ Stress test completed!"

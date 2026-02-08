#!/bin/bash
#
# Deploy Step Functions state machine to AWS
#
# Usage:
#   ./deploy.sh [state-machine-name] [region] [role-arn]
#
# Example:
#   ./deploy.sh manga-pipeline us-east-1 arn:aws:iam::123456789012:role/StepFunctionsRole
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STATE_MACHINE_NAME="${1:-manga-pipeline}"
REGION="${2:-us-east-1}"
ROLE_ARN="${3:-}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ASL_FILE="$SCRIPT_DIR/pipeline.asl.json"
TEMP_FILE="$SCRIPT_DIR/pipeline-deployed.asl.json"

echo -e "${GREEN}=== Step Functions Deployment ===${NC}\n"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Failed to get AWS account ID. Check your AWS credentials.${NC}"
    exit 1
fi

echo -e "${GREEN}Account ID:${NC} $ACCOUNT_ID"
echo -e "${GREEN}Region:${NC} $REGION"
echo -e "${GREEN}State Machine:${NC} $STATE_MACHINE_NAME"

# If role ARN not provided, construct default
if [ -z "$ROLE_ARN" ]; then
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/StepFunctionsExecutionRole"
    echo -e "${YELLOW}⚠️  No role ARN provided, using default: $ROLE_ARN${NC}"
fi

echo -e "${GREEN}Role ARN:${NC} $ROLE_ARN\n"

# Validate ASL file exists
if [ ! -f "$ASL_FILE" ]; then
    echo -e "${RED}❌ ASL file not found: $ASL_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: Validating ASL JSON...${NC}"
python3 "$SCRIPT_DIR/validate.py" "$ASL_FILE"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ASL validation failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}Step 2: Replacing placeholders...${NC}"
# Replace placeholders with actual values
sed -e "s/\${AWS::Region}/$REGION/g" \
    -e "s/\${AWS::AccountId}/$ACCOUNT_ID/g" \
    "$ASL_FILE" > "$TEMP_FILE"

echo -e "✓ Created temporary file: $TEMP_FILE"

echo -e "\n${GREEN}Step 3: Validating with AWS...${NC}"
aws stepfunctions validate-state-machine-definition \
    --definition file://"$TEMP_FILE" \
    --region "$REGION" \
    > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AWS validation passed${NC}"
else
    echo -e "${RED}❌ AWS validation failed${NC}"
    rm -f "$TEMP_FILE"
    exit 1
fi

# Check if state machine already exists
STATE_MACHINE_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}"

echo -e "\n${GREEN}Step 4: Checking if state machine exists...${NC}"
aws stepfunctions describe-state-machine \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --region "$REGION" \
    > /dev/null 2>&1

if [ $? -eq 0 ]; then
    # State machine exists, update it
    echo -e "${YELLOW}⚠️  State machine exists, updating...${NC}"

    aws stepfunctions update-state-machine \
        --state-machine-arn "$STATE_MACHINE_ARN" \
        --definition file://"$TEMP_FILE" \
        --region "$REGION" \
        > /dev/null

    echo -e "${GREEN}✓ State machine updated successfully${NC}"
else
    # State machine doesn't exist, create it
    echo -e "${GREEN}Creating new state machine...${NC}"

    # Check if role exists
    aws iam get-role --role-name "$(basename $ROLE_ARN)" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ IAM role not found: $ROLE_ARN${NC}"
        echo -e "${YELLOW}Please create the role first or provide a valid role ARN${NC}"
        rm -f "$TEMP_FILE"
        exit 1
    fi

    aws stepfunctions create-state-machine \
        --name "$STATE_MACHINE_NAME" \
        --definition file://"$TEMP_FILE" \
        --role-arn "$ROLE_ARN" \
        --region "$REGION" \
        > /dev/null

    echo -e "${GREEN}✓ State machine created successfully${NC}"
fi

# Clean up temp file
rm -f "$TEMP_FILE"

echo -e "\n${GREEN}=== Deployment Complete ===${NC}\n"
echo -e "${GREEN}State Machine ARN:${NC}"
echo -e "$STATE_MACHINE_ARN\n"

echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Deploy required Lambda functions"
echo -e "2. Set up EventBridge rule for scheduled execution:"
echo -e "   ${YELLOW}aws events put-rule --name manga-pipeline-daily --schedule-expression 'cron(0 12 * * ? *)'${NC}"
echo -e "3. Add Step Functions as target:"
echo -e "   ${YELLOW}aws events put-targets --rule manga-pipeline-daily --targets Id=1,Arn=$STATE_MACHINE_ARN,RoleArn=$ROLE_ARN${NC}"
echo -e "4. Start a test execution:"
echo -e "   ${YELLOW}aws stepfunctions start-execution --state-machine-arn $STATE_MACHINE_ARN --input '{}'${NC}"
echo -e "\n${GREEN}Monitor executions:${NC}"
echo -e "   ${YELLOW}https://console.aws.amazon.com/states/home?region=$REGION#/statemachines/view/$STATE_MACHINE_ARN${NC}"

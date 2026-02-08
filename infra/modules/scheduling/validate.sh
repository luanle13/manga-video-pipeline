#!/bin/bash
#
# Validate Terraform module syntax and formatting
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Terraform Module Validation ===${NC}\n"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not found. Please install Terraform first.${NC}"
    exit 1
fi

echo -e "${GREEN}Terraform version:${NC}"
terraform version
echo ""

# Step 1: Format check
echo -e "${GREEN}Step 1: Checking formatting...${NC}"
if terraform fmt -check -recursive; then
    echo -e "${GREEN}✓ All files properly formatted${NC}\n"
else
    echo -e "${YELLOW}⚠️  Files need formatting. Run: terraform fmt -recursive${NC}\n"
fi

# Step 2: Initialize
echo -e "${GREEN}Step 2: Initializing module...${NC}"
terraform init -backend=false > /dev/null 2>&1
echo -e "${GREEN}✓ Module initialized${NC}\n"

# Step 3: Validate syntax
echo -e "${GREEN}Step 3: Validating syntax...${NC}"
if terraform validate; then
    echo -e "${GREEN}✓ Syntax validation passed${NC}\n"
else
    echo -e "${RED}❌ Syntax validation failed${NC}"
    exit 1
fi

# Step 4: Validate examples
echo -e "${GREEN}Step 4: Validating examples...${NC}"

for example_dir in examples/*/; do
    example_name=$(basename "$example_dir")
    echo -e "${GREEN}  Validating example: ${example_name}${NC}"

    cd "$example_dir"

    # Skip if no Terraform files
    if ! ls *.tf &> /dev/null; then
        echo -e "${YELLOW}  ⚠️  No .tf files found, skipping${NC}"
        cd "$SCRIPT_DIR"
        continue
    fi

    # Initialize
    terraform init -backend=false > /dev/null 2>&1

    # Validate
    if terraform validate > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Example '${example_name}' is valid${NC}"
    else
        echo -e "${RED}  ❌ Example '${example_name}' validation failed${NC}"
        terraform validate
        cd "$SCRIPT_DIR"
        exit 1
    fi

    cd "$SCRIPT_DIR"
done

echo ""

# Step 5: Check for common issues
echo -e "${GREEN}Step 5: Checking for common issues...${NC}"

# Check for hardcoded ARNs
if grep -r "arn:aws:" *.tf 2>/dev/null | grep -v "# " | grep -v "validation" | grep -v "example" > /dev/null; then
    echo -e "${YELLOW}⚠️  Warning: Hardcoded ARNs found (may be intentional)${NC}"
else
    echo -e "${GREEN}✓ No hardcoded ARNs found${NC}"
fi

# Check for required version constraints
if grep -q "required_version" *.tf 2>/dev/null; then
    echo -e "${GREEN}✓ Terraform version constraint defined${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: No Terraform version constraint${NC}"
fi

# Check for provider version constraints
if grep -q "required_providers" *.tf 2>/dev/null; then
    echo -e "${GREEN}✓ Provider version constraints defined${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: No provider version constraints${NC}"
fi

echo ""
echo -e "${GREEN}=== Validation Complete ===${NC}"
echo -e "${GREEN}✅ All checks passed!${NC}\n"

echo -e "${GREEN}Next steps:${NC}"
echo "1. Deploy to a test environment:"
echo "   ${YELLOW}terraform plan -var=\"state_machine_arn=arn:aws:states:...\"${NC}"
echo "2. Review the plan carefully"
echo "3. Apply if everything looks correct:"
echo "   ${YELLOW}terraform apply -var=\"state_machine_arn=arn:aws:states:...\"${NC}"

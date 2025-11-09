#!/bin/bash
# Git hooks management script

set -e

HOOK_DIR=".git/hooks"
HOOKS_SOURCE_DIR=".github/hooks"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

install_hooks() {
    echo -e "${BLUE}📦 Installing Git hooks...${NC}"
    
    if [ ! -d "$HOOK_DIR" ]; then
        echo -e "${YELLOW}⚠️  .git directory not found. Are you in the repository root?${NC}"
        exit 1
    fi
    
    # Create hooks source directory if it doesn't exist
    mkdir -p "$HOOKS_SOURCE_DIR"
    
    # Copy pre-commit hook template
    cat > "$HOOKS_SOURCE_DIR/pre-commit" << 'HOOK_EOF'
#!/bin/bash
# Pre-commit hook for automatic code quality fixes
# Uses 'make code-quality-fix' to format staged Python files

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Running pre-commit code quality checks...${NC}"

# Get list of staged Python files
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$STAGED_PY_FILES" ]; then
    echo -e "${GREEN}✓ No Python files to check${NC}"
    exit 0
fi

echo -e "${YELLOW}📝 Formatting staged Python files...${NC}"
for FILE in $STAGED_PY_FILES; do
    echo -e "  ${YELLOW}•${NC} $FILE"
done

# Run make code-quality-fix
echo -e "${BLUE}Running: make code-quality-fix${NC}"
if make code-quality-fix > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Code formatted successfully${NC}"
    
    # Re-stage all Python files that were modified
    for FILE in $STAGED_PY_FILES; do
        git add "$FILE"
    done
    
    echo -e "${GREEN}✓ Changes re-staged${NC}"
else
    echo -e "${YELLOW}⚠️  Code quality fix failed, continuing anyway...${NC}"
fi

echo -e "${GREEN}✓ Pre-commit checks passed${NC}"
exit 0
HOOK_EOF
    
    # Install hooks
    if [ -f "$HOOKS_SOURCE_DIR/pre-commit" ]; then
        cp "$HOOKS_SOURCE_DIR/pre-commit" "$HOOK_DIR/pre-commit"
        chmod +x "$HOOK_DIR/pre-commit"
        echo -e "${GREEN}✓ pre-commit hook installed${NC}"
    fi
    
    echo -e "${GREEN}✓ Git hooks installed successfully${NC}"
    echo ""
    echo "Hooks installed:"
    ls -lh "$HOOK_DIR"/pre-commit 2>/dev/null || echo "  None"
}

uninstall_hooks() {
    echo -e "${BLUE}🗑️  Uninstalling Git hooks...${NC}"
    
    if [ -f "$HOOK_DIR/pre-commit" ]; then
        rm "$HOOK_DIR/pre-commit"
        echo -e "${GREEN}✓ pre-commit hook removed${NC}"
    fi
    
    echo -e "${GREEN}✓ Git hooks uninstalled${NC}"
}

show_status() {
    echo -e "${BLUE}📊 Git hooks status:${NC}"
    echo ""
    
    if [ -f "$HOOK_DIR/pre-commit" ]; then
        echo -e "  ${GREEN}✓${NC} pre-commit: installed"
    else
        echo -e "  ${YELLOW}✗${NC} pre-commit: not installed"
    fi
}

case "$1" in
    install)
        install_hooks
        ;;
    uninstall)
        uninstall_hooks
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        echo ""
        echo "Commands:"
        echo "  install    - Install Git hooks"
        echo "  uninstall  - Remove Git hooks"
        echo "  status     - Show hooks installation status"
        exit 1
        ;;
esac

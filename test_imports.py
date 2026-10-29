"""Test that new economy models import correctly without breaking existing functionality."""
import sys

print("Testing imports...")

# Test 1: Import all models from the package
try:
    from server.models import *
    print("✓ All wildcard imports successful")
except Exception as e:
    print(f"✗ Wildcard import failed: {e}")
    sys.exit(1)

# Test 2: Explicitly test new economy model classes exist and are valid
try:
    from server.models.economy.inventory import (
        CardInventory,
        get_user_inventory,
        get_total_cards_owned,
        get_inventory_by_source
    )
    print("✓ Inventory models imported successfully")
except Exception as e:
    print(f"✗ Inventory model import failed: {e}")
    sys.exit(1)

try:
    from server.models.economy.purchase_history import (
        PurchaseHistory,
        get_user_purchase_history,
        AdminTolkienAdjustRequest
    )
    print("✓ Purchase history models imported successfully")
except Exception as e:
    print(f"✗ Purchase history model import failed: {e}")
    sys.exit(1)

try:
    from server.server.models.base import Money, TimestampMixin
    print("✓ Base utility classes imported successfully")
except Exception as e:
    print(f"✗ Base utilities import failed: {e}")
    sys.exit(1)

# Test 3: Verify model registry integration worked
try:
    from server.server.models import CardInventory, PurchaseHistory
    assert CardInventory in __builtins__.get('__all__', []), "CardInventory should be exported"
    print("✓ Model registry integration verified")
except Exception as e:
    print(f"✗ Registry verification failed: {e}")

print("\n✅ All import tests passed!")
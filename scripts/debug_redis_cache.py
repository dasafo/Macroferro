#!/usr/bin/env python3
"""
Debug script para inspeccionar datos de cache en Redis
Útil para ver carritos, conversaciones y contexto de usuarios
"""

import redis
import json
import sys
from typing import Dict, Any, List
from pprint import pprint

def connect_to_redis() -> redis.Redis:
    """Conectar a Redis"""
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True,
            db=0
        )
        r.ping()
        print("✅ Conectado a Redis exitosamente")
        return r
    except redis.ConnectionError:
        print("❌ Error: No se puede conectar a Redis")
        print("💡 Asegúrate de que Docker Compose esté ejecutándose: make up")
        sys.exit(1)

def get_all_keys(r: redis.Redis) -> Dict[str, List[str]]:
    """Obtener todas las keys organizadas por tipo"""
    all_keys = r.keys("*")
    
    organized = {
        'cart': [],
        'conversation': [],
        'recent_products': [],
        'other': []
    }
    
    for key in all_keys:
        if key.startswith('cart:'):
            organized['cart'].append(key)
        elif key.startswith('conversation:'):
            organized['conversation'].append(key)
        elif key.startswith('recent_products:'):
            organized['recent_products'].append(key)
        else:
            organized['other'].append(key)
    
    return organized

def inspect_key(r: redis.Redis, key: str) -> Dict[str, Any]:
    """Inspeccionar una key específica"""
    key_type = r.type(key)
    ttl = r.ttl(key)
    
    result = {
        'key': key,
        'type': key_type,
        'ttl': ttl if ttl > 0 else 'No expira',
        'data': None
    }
    
    try:
        if key_type == 'string':
            data = r.get(key)
            try:
                # Intentar parsear como JSON
                result['data'] = json.loads(data)
            except json.JSONDecodeError:
                result['data'] = data
        elif key_type == 'hash':
            result['data'] = r.hgetall(key)
        elif key_type == 'list':
            result['data'] = r.lrange(key, 0, -1)
        elif key_type == 'set':
            result['data'] = list(r.smembers(key))
        else:
            result['data'] = f"Tipo {key_type} no soportado en este script"
    except Exception as e:
        result['data'] = f"Error al obtener datos: {str(e)}"
    
    return result

def main():
    """Función principal"""
    print("🔍 Inspeccionando Redis Cache Data\n")
    
    r = connect_to_redis()
    
    # Obtener todas las keys organizadas
    keys_by_type = get_all_keys(r)
    
    print("📊 Resumen de Keys en Redis:")
    for key_type, keys in keys_by_type.items():
        print(f"  {key_type}: {len(keys)} keys")
    print()
    
    # Mostrar carritos
    if keys_by_type['cart']:
        print("🛒 CARRITOS DE COMPRAS:")
        print("=" * 50)
        for cart_key in keys_by_type['cart']:
            data = inspect_key(r, cart_key)
            chat_id = cart_key.replace('cart:', '')
            print(f"\n📱 Chat ID: {chat_id}")
            print(f"⏰ TTL: {data['ttl']}")
            if data['data']:
                if isinstance(data['data'], dict) and 'items' in data['data']:
                    items = data['data']['items']
                    total = data['data'].get('total', 0)
                    print(f"🛍️  Items: {len(items)}")
                    print(f"💰 Total: ${total}")
                    for item in items:
                        print(f"   - {item.get('name', 'N/A')} x{item.get('quantity', 0)} = ${item.get('subtotal', 0)}")
                else:
                    print(f"📄 Data: {data['data']}")
            print("-" * 30)
    
    # Mostrar conversaciones
    if keys_by_type['conversation']:
        print("\n💬 CONVERSACIONES:")
        print("=" * 50)
        for conv_key in keys_by_type['conversation'][:3]:  # Solo las primeras 3
            data = inspect_key(r, conv_key)
            chat_id = conv_key.replace('conversation:', '')
            print(f"\n📱 Chat ID: {chat_id}")
            print(f"⏰ TTL: {data['ttl']}")
            if data['data'] and isinstance(data['data'], dict):
                print(f"📝 Mensajes: {len(data['data'])}")
                # Mostrar algunos campos clave
                for field, value in list(data['data'].items())[:5]:
                    print(f"   {field}: {str(value)[:100]}...")
            print("-" * 30)
    
    # Mostrar productos recientes
    if keys_by_type['recent_products']:
        print("\n🔍 PRODUCTOS RECIENTES:")
        print("=" * 50)
        for recent_key in keys_by_type['recent_products']:
            data = inspect_key(r, recent_key)
            chat_id = recent_key.replace('recent_products:', '')
            print(f"\n📱 Chat ID: {chat_id}")
            if data['data']:
                try:
                    products = json.loads(data['data']) if isinstance(data['data'], str) else data['data']
                    if isinstance(products, list):
                        print(f"📦 Productos guardados: {len(products)}")
                        for i, product in enumerate(products[:3]):  # Mostrar primeros 3
                            if isinstance(product, dict):
                                print(f"   {i+1}. {product.get('name', 'N/A')} (SKU: {product.get('sku', 'N/A')})")
                except:
                    print(f"📄 Data: {str(data['data'])[:100]}...")
            print("-" * 30)
    
    # Comando interactivo
    print(f"\n🔧 COMANDOS DISPONIBLES:")
    print("1. Ver key específica: python scripts/debug_redis_cache.py <key_name>")
    print("2. Conectar manualmente: docker compose exec redis redis-cli")
    print("3. Ver todas las keys: docker compose exec redis redis-cli KEYS '*'")
    
    # Si se pasó una key específica como argumento
    if len(sys.argv) > 1:
        specific_key = sys.argv[1]
        print(f"\n🎯 INSPECCIONANDO KEY ESPECÍFICA: {specific_key}")
        print("=" * 60)
        if r.exists(specific_key):
            data = inspect_key(r, specific_key)
            pprint(data, width=100, depth=3)
        else:
            print(f"❌ La key '{specific_key}' no existe")
            print("\n💡 Keys disponibles:")
            for key_type, keys in keys_by_type.items():
                if keys:
                    print(f"  {key_type}: {keys[:5]}")  # Mostrar primeras 5

if __name__ == "__main__":
    main() 
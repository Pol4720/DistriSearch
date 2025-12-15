#!/usr/bin/env python3
"""
DistriSearch Data Migration Script
Export and import data between DistriSearch instances
"""

import asyncio
import argparse
import json
import gzip
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiohttp


class DataMigrator:
    """Handle data migration between DistriSearch instances"""
    
    def __init__(self, api_url: str, batch_size: int = 100):
        self.api_url = api_url.rstrip('/')
        self.batch_size = batch_size
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> bool:
        """Check if API is available"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
        except Exception:
            return False
    
    async def get_total_documents(self) -> int:
        """Get total document count"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/documents",
                params={"limit": 1},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("total", 0)
                return 0
        except Exception:
            return 0
    
    async def fetch_documents(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch documents with pagination"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/documents",
                params={"skip": skip, "limit": limit},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("documents", [])
                return []
        except Exception as e:
            print(f"Error fetching documents: {e}")
            return []
    
    async def export_documents(
        self,
        output_path: str,
        compress: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Export all documents to a file"""
        total = await self.get_total_documents()
        
        if total == 0:
            return {"success": False, "error": "No documents to export"}
        
        all_documents = []
        exported = 0
        
        for skip in range(0, total, self.batch_size):
            documents = await self.fetch_documents(skip, self.batch_size)
            all_documents.extend(documents)
            exported += len(documents)
            
            if progress_callback:
                progress_callback(exported, total)
        
        # Create export data
        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "source": self.api_url,
            "total_documents": len(all_documents),
            "documents": all_documents
        }
        
        # Write to file
        path = Path(output_path)
        
        if compress or output_path.endswith(".gz"):
            if not output_path.endswith(".gz"):
                output_path = f"{output_path}.gz"
                path = Path(output_path)
            
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)
        
        return {
            "success": True,
            "path": str(path),
            "documents_exported": len(all_documents),
            "compressed": compress or output_path.endswith(".gz")
        }
    
    async def import_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Import a single document"""
        # Remove internal fields
        clean_doc = {
            "title": doc.get("title", "Untitled"),
            "content": doc.get("content", ""),
            "metadata": doc.get("metadata", {})
        }
        
        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/documents",
                json=clean_doc,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return {"success": True, "id": result.get("id")}
                else:
                    error = await response.text()
                    return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def import_documents(
        self,
        input_path: str,
        skip_existing: bool = False,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Import documents from a file"""
        path = Path(input_path)
        
        if not path.exists():
            return {"success": False, "error": f"File not found: {input_path}"}
        
        # Read import data
        try:
            if input_path.endswith(".gz"):
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    import_data = json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    import_data = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}
        
        documents = import_data.get("documents", [])
        
        if not documents:
            return {"success": False, "error": "No documents found in file"}
        
        total = len(documents)
        imported = 0
        failed = 0
        skipped = 0
        
        for i, doc in enumerate(documents):
            result = await self.import_document(doc)
            
            if result["success"]:
                imported += 1
            else:
                failed += 1
            
            if progress_callback:
                progress_callback(i + 1, total, result)
        
        return {
            "success": True,
            "total": total,
            "imported": imported,
            "failed": failed,
            "skipped": skipped
        }
    
    async def delete_all_documents(self, confirm: bool = False) -> Dict[str, Any]:
        """Delete all documents (use with caution!)"""
        if not confirm:
            return {"success": False, "error": "Deletion not confirmed"}
        
        total = await self.get_total_documents()
        
        if total == 0:
            return {"success": True, "deleted": 0}
        
        deleted = 0
        failed = 0
        
        # Fetch and delete in batches
        for skip in range(0, total, self.batch_size):
            documents = await self.fetch_documents(0, self.batch_size)
            
            if not documents:
                break
            
            for doc in documents:
                doc_id = doc.get("id")
                if doc_id:
                    try:
                        async with self.session.delete(
                            f"{self.api_url}/api/v1/documents/{doc_id}",
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status in [200, 204]:
                                deleted += 1
                            else:
                                failed += 1
                    except Exception:
                        failed += 1
            
            print(f"Deleted: {deleted}, Failed: {failed}")
        
        return {
            "success": True,
            "deleted": deleted,
            "failed": failed
        }


def print_export_progress(exported: int, total: int):
    """Print export progress"""
    percent = (exported / total * 100) if total > 0 else 0
    print(f"\rExporting: {exported}/{total} ({percent:.1f}%)", end="", flush=True)


def print_import_progress(current: int, total: int, result: Dict[str, Any]):
    """Print import progress"""
    percent = (current / total * 100) if total > 0 else 0
    status = "✓" if result.get("success") else "✗"
    print(f"\rImporting: {current}/{total} ({percent:.1f}%) {status}", end="", flush=True)


async def main():
    parser = argparse.ArgumentParser(description="DistriSearch Data Migration")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export documents to file")
    export_parser.add_argument("--api-url", default="http://localhost:8000", help="Source API URL")
    export_parser.add_argument("--output", "-o", required=True, help="Output file path")
    export_parser.add_argument("--no-compress", action="store_true", help="Don't compress output")
    export_parser.add_argument("--batch-size", type=int, default=100, help="Batch size for fetching")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import documents from file")
    import_parser.add_argument("--api-url", default="http://localhost:8000", help="Target API URL")
    import_parser.add_argument("--input", "-i", required=True, help="Input file path")
    import_parser.add_argument("--skip-existing", action="store_true", help="Skip existing documents")
    import_parser.add_argument("--batch-size", type=int, default=100, help="Batch size for importing")
    
    # Migrate command (export from source, import to target)
    migrate_parser = subparsers.add_parser("migrate", help="Migrate data between instances")
    migrate_parser.add_argument("--source", required=True, help="Source API URL")
    migrate_parser.add_argument("--target", required=True, help="Target API URL")
    migrate_parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete all documents (DANGEROUS!)")
    delete_parser.add_argument("--api-url", default="http://localhost:8000", help="API URL")
    delete_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "export":
        async with DataMigrator(args.api_url, args.batch_size) as migrator:
            if not await migrator.check_health():
                print(f"Error: API at {args.api_url} is not available")
                sys.exit(1)
            
            print(f"Exporting documents from {args.api_url}...")
            result = await migrator.export_documents(
                args.output,
                compress=not args.no_compress,
                progress_callback=print_export_progress
            )
            
            print()
            if result["success"]:
                print(f"\n✓ Export complete!")
                print(f"  Documents exported: {result['documents_exported']}")
                print(f"  Output file: {result['path']}")
                print(f"  Compressed: {result['compressed']}")
            else:
                print(f"\n✗ Export failed: {result.get('error')}")
                sys.exit(1)
    
    elif args.command == "import":
        async with DataMigrator(args.api_url, args.batch_size) as migrator:
            if not await migrator.check_health():
                print(f"Error: API at {args.api_url} is not available")
                sys.exit(1)
            
            print(f"Importing documents to {args.api_url}...")
            result = await migrator.import_documents(
                args.input,
                skip_existing=args.skip_existing,
                progress_callback=print_import_progress
            )
            
            print()
            if result["success"]:
                print(f"\n✓ Import complete!")
                print(f"  Total: {result['total']}")
                print(f"  Imported: {result['imported']}")
                print(f"  Failed: {result['failed']}")
                print(f"  Skipped: {result['skipped']}")
            else:
                print(f"\n✗ Import failed: {result.get('error')}")
                sys.exit(1)
    
    elif args.command == "migrate":
        # Export from source
        print(f"Starting migration from {args.source} to {args.target}")
        
        temp_file = f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
        
        async with DataMigrator(args.source, args.batch_size) as source_migrator:
            if not await source_migrator.check_health():
                print(f"Error: Source API at {args.source} is not available")
                sys.exit(1)
            
            print(f"Exporting from source...")
            export_result = await source_migrator.export_documents(
                temp_file,
                compress=True,
                progress_callback=print_export_progress
            )
            
            if not export_result["success"]:
                print(f"\n✗ Export failed: {export_result.get('error')}")
                sys.exit(1)
        
        print()
        
        # Import to target
        async with DataMigrator(args.target, args.batch_size) as target_migrator:
            if not await target_migrator.check_health():
                print(f"Error: Target API at {args.target} is not available")
                sys.exit(1)
            
            print(f"Importing to target...")
            import_result = await target_migrator.import_documents(
                temp_file,
                progress_callback=print_import_progress
            )
            
            print()
            if import_result["success"]:
                print(f"\n✓ Migration complete!")
                print(f"  Total: {import_result['total']}")
                print(f"  Imported: {import_result['imported']}")
                print(f"  Failed: {import_result['failed']}")
            else:
                print(f"\n✗ Import failed: {import_result.get('error')}")
                sys.exit(1)
        
        # Cleanup temp file
        try:
            Path(temp_file).unlink()
            print(f"  Cleaned up temp file: {temp_file}")
        except Exception:
            pass
    
    elif args.command == "delete":
        if not args.confirm:
            print("⚠️  WARNING: This will delete ALL documents!")
            print("Use --confirm flag to proceed")
            sys.exit(1)
        
        async with DataMigrator(args.api_url) as migrator:
            if not await migrator.check_health():
                print(f"Error: API at {args.api_url} is not available")
                sys.exit(1)
            
            print(f"Deleting all documents from {args.api_url}...")
            result = await migrator.delete_all_documents(confirm=True)
            
            if result["success"]:
                print(f"\n✓ Deletion complete!")
                print(f"  Deleted: {result['deleted']}")
                print(f"  Failed: {result['failed']}")
            else:
                print(f"\n✗ Deletion failed: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())

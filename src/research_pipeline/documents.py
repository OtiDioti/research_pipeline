"""Immutable, scoped reads of stopped writers' drafts before canonical publication."""
import hashlib
from pathlib import Path

from . import jobs, verification, workspace

PAGE_CHARACTERS = 8192
LIST_LIMIT = 32


class Documents:
    def __init__(self, project, state):
        self.project, self.state = project, state
        self.root = workspace.safe_path(project, '.research_pipeline/documents')
        self.root.mkdir(exist_ok=True)

    def capture(self, record, kind, drafts, protected=()):
        # Other contexts/jobs may still write science. Read only this writer's
        # private batch after its complete service/descendant cleanup is confirmed.
        if record.get('cleanup_ok') is not True or record.get('documents_captured'):
            return
        try:
            workspace.regular_tree(drafts)
            paths = [path for path in sorted(drafts.rglob('*')) if path.is_file()]
            for path in paths:
                rel = path.relative_to(drafts).as_posix()
                if (path.suffix != '.md' or path.name == 'FOLDER_CONTENT.md'
                        or any(part.startswith('.') for part in Path(rel).parts)
                        or not workspace.allowed_science(rel, record['task_id'], protected)):
                    raise workspace.InputError(f'Invalid scientific document destination: {rel}')
            for path in paths:
                rel = path.relative_to(drafts).as_posix()
                raw = verification.read_bytes(path, None)  # bounded, no symlinks/FIFOs
                content = raw.decode('utf-8')
                digest = hashlib.sha256(raw).hexdigest()
                source_id = record['context_id' if kind == 'context' else 'job_id']
                document_id = hashlib.sha256(f'{kind}:{source_id}:{rel}:{digest}'.encode()).hexdigest()
                target = self.root / (document_id + '.md')
                if not target.exists():
                    workspace.atomic_text(target, content)
                    target.chmod(0o400)
                elif hashlib.sha256(verification.read_bytes(target, None)).hexdigest() != digest:
                    raise workspace.InputError('Retained document changed; refusing to replace it')
                metadata = {'document_id': document_id, 'task_id': record['task_id'],
                            'source_kind': kind, 'source_id': source_id,
                            'path': rel, 'sha256': digest, 'bytes': len(raw)}
                self.state.setdefault('documents', {})[document_id] = metadata
                ids = record.setdefault('document_ids', [])
                if document_id not in ids:
                    ids.append(document_id)
        except (OSError, ValueError) as exc:
            # Preserve valid partial snapshots and expose failure without changing
            # actual process cleanup or authorizing publication of an invalid batch.
            record['document_snapshot_error'] = f'{type(exc).__name__}: {exc}'
        record['documents_captured'] = True

    def allowed(self, reader, document):
        owner = document['task_id']
        return (reader == 'primary' or reader == owner
                or self.state['tasks'][owner].get('parent_task') == reader)

    def list(self, reader, offset=0):
        self.check_offset(offset)
        visible = [document for document in reversed(list(self.state.get('documents', {}).values()))
                   if self.allowed(reader, document)]
        page = visible[offset:offset + LIST_LIMIT]
        errors = [{'task_id': record['task_id'], 'source_id': record.get('context_id', record.get('job_id')),
                   'error': record['document_snapshot_error']}
                  for record in (*self.state['contexts'].values(), *self.state['jobs'].values())
                  if record.get('document_snapshot_error') and self.allowed(reader, record)]
        return {'documents': page, 'documents_total': len(visible), 'offset': offset,
                'next_offset': offset + len(page) if offset + len(page) < len(visible) else None,
                'document_errors': errors[-LIST_LIMIT:]}

    def raw(self, reader, document_id):
        document = self.state.get("documents", {}).get(document_id)
        if not document or not self.allowed(reader, document):
            raise jobs.JobError("Unknown document or foreign logical task")
        raw = verification.read_bytes(self.root / (document_id + ".md"), None)
        if hashlib.sha256(raw).hexdigest() != document["sha256"]:
            raise jobs.JobError("Document integrity check failed")
        return raw

    def read(self, reader, document_id, offset=0):
        self.check_offset(offset)
        document = self.state.get('documents', {}).get(document_id) if isinstance(document_id, str) else None
        if not document or not self.allowed(reader, document):
            raise jobs.JobError('Unknown document or document belongs to another logical task')
        # Resolve only controller-generated IDs; callers cannot supply a host path.
        raw = self.raw(reader, document_id)
        text = raw.decode('utf-8')
        content = text[offset:offset + PAGE_CHARACTERS]
        end = offset + len(content)
        return {**document, 'content': content, 'offset': offset,
                'next_offset': end if end < len(text) else None, 'characters_total': len(text)}

    @staticmethod
    def check_offset(offset):
        if type(offset) is not int or offset < 0:
            raise jobs.JobError('Document offset must be a nonnegative integer')

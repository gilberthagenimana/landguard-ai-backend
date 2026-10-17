# LandGuard AI — Transaction Evidence Management

## Overview

The evidence management feature allows authorized Officers to upload, manage, and review supporting documents for land transaction verification. This strengthens the verification process by providing a secure way to handle sale agreements, payment receipts, and other supporting evidence.

> **IMPORTANT**: An uploaded document is **supporting evidence**, NOT conclusive proof of payment, legal ownership, or authorization to transfer land. The system never automatically claims that a receipt is genuine or that payment has been completed merely because a file was uploaded.

## Evidence States

| State | Meaning |
|---|---|
| `NOT_PROVIDED` | No evidence has been uploaded for this transaction |
| `UPLOADED` | Evidence has been uploaded and is awaiting review |
| `UNDER_REVIEW` | An authorized reviewer is actively reviewing the evidence |
| `VERIFIED_FOR_REVIEW` | An authorized reviewer completed the defined checks. Does NOT imply independent confirmation from a bank, government system, or other external institution |
| `NEEDS_CLARIFICATION` | Additional information or clarification is required |
| `INCONSISTENT` | Evidence contains inconsistencies with transaction records |

## Role Permissions

| Action | ADMIN | OFFICER | AUDITOR |
|---|---|---|---|
| Upload evidence | No | Yes | No |
| View evidence list | Yes | Yes | Yes |
| Download evidence | Yes | Yes | Yes |
| Review evidence | No | Yes | No |
| View review history | Yes | Yes | Yes |

## File Upload Rules

| Rule | Value |
|---|---|
| Allowed types | PDF, JPEG, PNG |
| Max file size | 10 MB (configurable) |
| Storage location | Server-side, non-public directory |
| Filename | Server-generated UUID (original filename preserved in database) |
| Hash | SHA-256 cryptographic hash stored for integrity |

## API Endpoints

### Upload Evidence
```
POST /api/evidence/transactions/{transaction_id}
Content-Type: multipart/form-data

Parameters:
- file: The document file (required)
- document_type: SALE_AGREEMENT, PAYMENT_RECEIPT, IDENTITY_DOCUMENT, OWNERSHIP_PROOF, SUPPORTING_DOCUMENT
- stated_payment_amount: Optional payment amount stated in the document
- stated_payment_date: Optional payment date stated in the document
- payment_reference: Optional payment reference number
- notes: Optional notes
```

### List Transaction Evidence
```
GET /api/evidence/transactions/{transaction_id}
```

### Download Evidence
```
GET /api/evidence/{evidence_id}
```

### Review Evidence
```
PUT /api/evidence/{evidence_id}/review
Content-Type: application/json

{
  "status": "UNDER_REVIEW" | "VERIFIED_FOR_REVIEW" | "NEEDS_CLARIFICATION" | "INCONSISTENT",
  "review_notes": "Explanation of review findings"
}
```

### View Review History
```
GET /api/evidence/{evidence_id}/review-history
```

## Security Measures

1. **File validation**: Extension, MIME type, and file content verified
2. **Size limits**: Configurable maximum file size
3. **Secure storage**: Files stored in non-public directory with server-generated names
4. **Path traversal prevention**: Original filenames never used for storage
5. **Integrity checking**: SHA-256 hash stored for each file
6. **Access control**: All endpoints require authentication and authorization
7. **Audit logging**: All upload, download, and review actions logged
8. **Review history preservation**: Previous review records never deleted

## Integration with Verification

Evidence completeness and review outcomes are included in the transaction verification workflow:
- Missing evidence generates a review warning
- Inconsistent evidence generates a risk indicator
- Evidence review status is visible in transaction details
- Evidence does NOT automatically complete a transaction or transfer ownership

## Limitations

1. **No malware scanning**: Files are not scanned for malware in the current implementation
2. **No OCR/AI analysis**: Documents are not automatically analyzed for content
3. **No external verification**: System cannot verify authenticity with banks or government systems
4. **Storage dependency**: Files stored on server filesystem; cloud storage not yet implemented
5. **No file preview**: Documents must be downloaded to be viewed

## Testing

Evidence tests cover:
- Successful upload of allowed file types
- Rejection of disallowed file types
- Rejection of oversized files
- Invalid transaction references
- Unauthorized access attempts
- Evidence linked to correct transaction
- Review status transitions
- Audit logging preservation
- Confirmation that upload alone never completes a land transfer

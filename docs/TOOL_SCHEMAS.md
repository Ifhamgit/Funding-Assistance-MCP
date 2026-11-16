# MCP Tool Schemas (generated)

Generated from the running server by `uv run python -m funding_mcp.schema_doc`; `tests/test_schema_doc.py` fails if
this file differs from the code. Business meaning, roles and errors: [SPEC.md](SPEC.md) §5. Every tool can also return
the error envelope of SPEC §5.3 with `isError: true` (not covered by `outputSchema`, per MCP).

## `get_current_staff`

Who am I? Returns the staff identity this server acts as: name, role and nonprofit. Any role.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {},
  "title": "get_current_staffArguments"
}
```

**Output schema**

```json
{
  "properties": {
    "staff_id": {
      "title": "Staff Id",
      "type": "string"
    },
    "display_name": {
      "title": "Display Name",
      "type": "string"
    },
    "role": {
      "enum": [
        "case_worker",
        "program_manager",
        "finance"
      ],
      "title": "Role",
      "type": "string"
    },
    "nonprofit_id": {
      "title": "Nonprofit Id",
      "type": "string"
    },
    "nonprofit_name": {
      "title": "Nonprofit Name",
      "type": "string"
    }
  },
  "required": [
    "staff_id",
    "display_name",
    "role",
    "nonprofit_id",
    "nonprofit_name"
  ],
  "title": "Staff",
  "type": "object"
}
```

## `list_participants`

List participants of your nonprofit, optionally filtered by name. Any role. Read-only.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "name_contains": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Case-insensitive name filter",
      "title": "Name Contains"
    }
  },
  "title": "list_participantsArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "Participant": {
      "properties": {
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "full_name": {
          "title": "Full Name",
          "type": "string"
        }
      },
      "required": [
        "participant_id",
        "full_name"
      ],
      "title": "Participant",
      "type": "object"
    }
  },
  "properties": {
    "participants": {
      "items": {
        "$ref": "#/$defs/Participant"
      },
      "title": "Participants",
      "type": "array"
    }
  },
  "required": [
    "participants"
  ],
  "title": "ParticipantList",
  "type": "object"
}
```

## `list_funds`

List your nonprofit's grant funds with their fixed allocations. Any role. Read-only.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {},
  "title": "list_fundsArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "Fund": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation"
      ],
      "title": "Fund",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    }
  },
  "properties": {
    "funds": {
      "items": {
        "$ref": "#/$defs/Fund"
      },
      "title": "Funds",
      "type": "array"
    }
  },
  "required": [
    "funds"
  ],
  "title": "FundList",
  "type": "object"
}
```

## `get_request`

Get one assistance request with its status, decision and payment. Any role. Read-only.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "request_id": {
      "description": "ID returned by create_assistance_request",
      "maxLength": 100,
      "minLength": 1,
      "title": "Request Id",
      "type": "string"
    }
  },
  "required": [
    "request_id"
  ],
  "title": "get_requestArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    }
  },
  "properties": {
    "request": {
      "$ref": "#/$defs/AssistanceRequest"
    }
  },
  "required": [
    "request"
  ],
  "title": "RequestResult",
  "type": "object"
}
```

## `list_requests`

List your nonprofit's assistance requests, newest first, with optional filters. Any role. Read-only.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "status": {
      "anyOf": [
        {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Filter by status",
      "title": "Status"
    },
    "fund_id": {
      "anyOf": [
        {
          "maxLength": 100,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Filter by fund",
      "title": "Fund Id"
    },
    "participant_id": {
      "anyOf": [
        {
          "maxLength": 100,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Filter by participant",
      "title": "Participant Id"
    },
    "limit": {
      "default": 50,
      "description": "Max results, newest first",
      "maximum": 100,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    }
  },
  "title": "list_requestsArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    }
  },
  "properties": {
    "requests": {
      "items": {
        "$ref": "#/$defs/AssistanceRequest"
      },
      "title": "Requests",
      "type": "array"
    }
  },
  "required": [
    "requests"
  ],
  "title": "RequestList",
  "type": "object"
}
```

## `get_funding_summary`

Funding summary per fund and totals: allocation, committed, paid, available (= allocation - committed - paid) and pending (not reserved). Any role. Read-only.

Annotations: readOnly=True, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "fund_id": {
      "anyOf": [
        {
          "maxLength": 100,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Only this fund; omit for all funds",
      "title": "Fund Id"
    }
  },
  "title": "get_funding_summaryArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "FundSummary": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money",
          "description": "Reserved by approved, unpaid requests"
        },
        "paid": {
          "$ref": "#/$defs/Money",
          "description": "Recorded payments"
        },
        "available": {
          "$ref": "#/$defs/Money",
          "description": "allocation - committed - paid"
        },
        "pending": {
          "$ref": "#/$defs/Money",
          "description": "Sum of pending requests; informational, NOT reserved"
        },
        "request_counts": {
          "$ref": "#/$defs/RequestCounts"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation",
        "committed",
        "paid",
        "available",
        "pending",
        "request_counts"
      ],
      "title": "FundSummary",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "RequestCounts": {
      "properties": {
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "approved": {
          "title": "Approved",
          "type": "integer"
        },
        "rejected": {
          "title": "Rejected",
          "type": "integer"
        },
        "paid": {
          "title": "Paid",
          "type": "integer"
        }
      },
      "required": [
        "pending",
        "approved",
        "rejected",
        "paid"
      ],
      "title": "RequestCounts",
      "type": "object"
    },
    "Totals": {
      "properties": {
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money"
        },
        "paid": {
          "$ref": "#/$defs/Money"
        },
        "available": {
          "$ref": "#/$defs/Money"
        },
        "pending": {
          "$ref": "#/$defs/Money"
        }
      },
      "required": [
        "allocation",
        "committed",
        "paid",
        "available",
        "pending"
      ],
      "title": "Totals",
      "type": "object"
    }
  },
  "properties": {
    "funds": {
      "items": {
        "$ref": "#/$defs/FundSummary"
      },
      "title": "Funds",
      "type": "array"
    },
    "totals": {
      "$ref": "#/$defs/Totals"
    }
  },
  "required": [
    "funds",
    "totals"
  ],
  "title": "FundingSummary",
  "type": "object"
}
```

## `create_assistance_request`

Submit an assistance request (case workers only). It starts pending and reserves NO money; a program manager must approve it.

Annotations: readOnly=False, idempotent=False, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "participant_id": {
      "description": "Existing participant of your nonprofit",
      "maxLength": 100,
      "minLength": 1,
      "title": "Participant Id",
      "type": "string"
    },
    "fund_id": {
      "description": "Fund of your nonprofit to pay from",
      "maxLength": 100,
      "minLength": 1,
      "title": "Fund Id",
      "type": "string"
    },
    "purpose": {
      "description": "Expense category",
      "enum": [
        "rent",
        "utilities",
        "transportation",
        "other"
      ],
      "title": "Purpose",
      "type": "string"
    },
    "amount": {
      "description": "USD decimal string > 0, max 2 decimals, e.g. \"300.00\"",
      "pattern": "^(0|[1-9][0-9]{0,6})(\\.[0-9]{1,2})?$",
      "title": "Amount",
      "type": "string"
    },
    "description": {
      "anyOf": [
        {
          "maxLength": 500,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Details; required when purpose is other",
      "title": "Description"
    },
    "idempotency_key": {
      "anyOf": [
        {
          "pattern": "^[A-Za-z0-9_.:-]{1,100}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional; resending the same key returns the original request instead of a duplicate",
      "title": "Idempotency Key"
    }
  },
  "required": [
    "participant_id",
    "fund_id",
    "purpose",
    "amount"
  ],
  "title": "create_assistance_requestArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "FundSummary": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money",
          "description": "Reserved by approved, unpaid requests"
        },
        "paid": {
          "$ref": "#/$defs/Money",
          "description": "Recorded payments"
        },
        "available": {
          "$ref": "#/$defs/Money",
          "description": "allocation - committed - paid"
        },
        "pending": {
          "$ref": "#/$defs/Money",
          "description": "Sum of pending requests; informational, NOT reserved"
        },
        "request_counts": {
          "$ref": "#/$defs/RequestCounts"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation",
        "committed",
        "paid",
        "available",
        "pending",
        "request_counts"
      ],
      "title": "FundSummary",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    },
    "RequestCounts": {
      "properties": {
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "approved": {
          "title": "Approved",
          "type": "integer"
        },
        "rejected": {
          "title": "Rejected",
          "type": "integer"
        },
        "paid": {
          "title": "Paid",
          "type": "integer"
        }
      },
      "required": [
        "pending",
        "approved",
        "rejected",
        "paid"
      ],
      "title": "RequestCounts",
      "type": "object"
    }
  },
  "properties": {
    "request": {
      "$ref": "#/$defs/AssistanceRequest"
    },
    "fund": {
      "$ref": "#/$defs/FundSummary",
      "description": "The request's fund after this call"
    },
    "replayed": {
      "description": "True if this call repeated an already-applied action and changed nothing",
      "title": "Replayed",
      "type": "boolean"
    }
  },
  "required": [
    "request",
    "fund",
    "replayed"
  ],
  "title": "MutationResult",
  "type": "object"
}
```

## `approve_request`

Approve a pending request (program managers only). Atomically reserves the full amount from its fund; fails with INSUFFICIENT_FUNDS if the fund's available balance is too low. Repeating it is safe.

Annotations: readOnly=False, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "request_id": {
      "description": "ID returned by create_assistance_request",
      "maxLength": 100,
      "minLength": 1,
      "title": "Request Id",
      "type": "string"
    }
  },
  "required": [
    "request_id"
  ],
  "title": "approve_requestArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "FundSummary": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money",
          "description": "Reserved by approved, unpaid requests"
        },
        "paid": {
          "$ref": "#/$defs/Money",
          "description": "Recorded payments"
        },
        "available": {
          "$ref": "#/$defs/Money",
          "description": "allocation - committed - paid"
        },
        "pending": {
          "$ref": "#/$defs/Money",
          "description": "Sum of pending requests; informational, NOT reserved"
        },
        "request_counts": {
          "$ref": "#/$defs/RequestCounts"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation",
        "committed",
        "paid",
        "available",
        "pending",
        "request_counts"
      ],
      "title": "FundSummary",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    },
    "RequestCounts": {
      "properties": {
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "approved": {
          "title": "Approved",
          "type": "integer"
        },
        "rejected": {
          "title": "Rejected",
          "type": "integer"
        },
        "paid": {
          "title": "Paid",
          "type": "integer"
        }
      },
      "required": [
        "pending",
        "approved",
        "rejected",
        "paid"
      ],
      "title": "RequestCounts",
      "type": "object"
    }
  },
  "properties": {
    "request": {
      "$ref": "#/$defs/AssistanceRequest"
    },
    "fund": {
      "$ref": "#/$defs/FundSummary",
      "description": "The request's fund after this call"
    },
    "replayed": {
      "description": "True if this call repeated an already-applied action and changed nothing",
      "title": "Replayed",
      "type": "boolean"
    }
  },
  "required": [
    "request",
    "fund",
    "replayed"
  ],
  "title": "MutationResult",
  "type": "object"
}
```

## `reject_request`

Reject a pending request (program managers only). Funding is unchanged. Repeating it is safe.

Annotations: readOnly=False, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "request_id": {
      "description": "ID returned by create_assistance_request",
      "maxLength": 100,
      "minLength": 1,
      "title": "Request Id",
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 500,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Why it was rejected",
      "title": "Reason"
    }
  },
  "required": [
    "request_id"
  ],
  "title": "reject_requestArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "FundSummary": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money",
          "description": "Reserved by approved, unpaid requests"
        },
        "paid": {
          "$ref": "#/$defs/Money",
          "description": "Recorded payments"
        },
        "available": {
          "$ref": "#/$defs/Money",
          "description": "allocation - committed - paid"
        },
        "pending": {
          "$ref": "#/$defs/Money",
          "description": "Sum of pending requests; informational, NOT reserved"
        },
        "request_counts": {
          "$ref": "#/$defs/RequestCounts"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation",
        "committed",
        "paid",
        "available",
        "pending",
        "request_counts"
      ],
      "title": "FundSummary",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    },
    "RequestCounts": {
      "properties": {
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "approved": {
          "title": "Approved",
          "type": "integer"
        },
        "rejected": {
          "title": "Rejected",
          "type": "integer"
        },
        "paid": {
          "title": "Paid",
          "type": "integer"
        }
      },
      "required": [
        "pending",
        "approved",
        "rejected",
        "paid"
      ],
      "title": "RequestCounts",
      "type": "object"
    }
  },
  "properties": {
    "request": {
      "$ref": "#/$defs/AssistanceRequest"
    },
    "fund": {
      "$ref": "#/$defs/FundSummary",
      "description": "The request's fund after this call"
    },
    "replayed": {
      "description": "True if this call repeated an already-applied action and changed nothing",
      "title": "Replayed",
      "type": "boolean"
    }
  },
  "required": [
    "request",
    "fund",
    "replayed"
  ],
  "title": "MutationResult",
  "type": "object"
}
```

## `record_payment`

Record the simulated payment of an approved request (finance only), for the full approved amount. Moves it from committed to paid; available is unchanged. Succeeds once; retries return the original payment.

Annotations: readOnly=False, idempotent=True, destructive=False

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "request_id": {
      "description": "ID returned by create_assistance_request",
      "maxLength": 100,
      "minLength": 1,
      "title": "Request Id",
      "type": "string"
    },
    "payment_reference": {
      "anyOf": [
        {
          "maxLength": 100,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Simulated check/transfer reference",
      "title": "Payment Reference"
    }
  },
  "required": [
    "request_id"
  ],
  "title": "record_paymentArguments"
}
```

**Output schema**

```json
{
  "$defs": {
    "AssistanceRequest": {
      "properties": {
        "request_id": {
          "title": "Request Id",
          "type": "string"
        },
        "participant_id": {
          "title": "Participant Id",
          "type": "string"
        },
        "participant_name": {
          "title": "Participant Name",
          "type": "string"
        },
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "fund_name": {
          "title": "Fund Name",
          "type": "string"
        },
        "purpose": {
          "enum": [
            "rent",
            "utilities",
            "transportation",
            "other"
          ],
          "title": "Purpose",
          "type": "string"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Description"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "status": {
          "enum": [
            "pending",
            "approved",
            "rejected",
            "paid"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "decided_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided By"
        },
        "decided_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decided At"
        },
        "decision_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Decision Reason"
        },
        "payment": {
          "anyOf": [
            {
              "$ref": "#/$defs/Payment"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "request_id",
        "participant_id",
        "participant_name",
        "fund_id",
        "fund_name",
        "purpose",
        "description",
        "amount",
        "status",
        "created_by",
        "created_at",
        "decided_by",
        "decided_at",
        "decision_reason",
        "payment"
      ],
      "title": "AssistanceRequest",
      "type": "object"
    },
    "FundSummary": {
      "properties": {
        "fund_id": {
          "title": "Fund Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "allocation": {
          "$ref": "#/$defs/Money"
        },
        "committed": {
          "$ref": "#/$defs/Money",
          "description": "Reserved by approved, unpaid requests"
        },
        "paid": {
          "$ref": "#/$defs/Money",
          "description": "Recorded payments"
        },
        "available": {
          "$ref": "#/$defs/Money",
          "description": "allocation - committed - paid"
        },
        "pending": {
          "$ref": "#/$defs/Money",
          "description": "Sum of pending requests; informational, NOT reserved"
        },
        "request_counts": {
          "$ref": "#/$defs/RequestCounts"
        }
      },
      "required": [
        "fund_id",
        "name",
        "allocation",
        "committed",
        "paid",
        "available",
        "pending",
        "request_counts"
      ],
      "title": "FundSummary",
      "type": "object"
    },
    "Money": {
      "properties": {
        "cents": {
          "description": "Exact amount in integer US cents",
          "minimum": 0,
          "title": "Cents",
          "type": "integer"
        },
        "usd": {
          "description": "Same amount as a decimal string, e.g. \"300.00\"",
          "title": "Usd",
          "type": "string"
        }
      },
      "required": [
        "cents",
        "usd"
      ],
      "title": "Money",
      "type": "object"
    },
    "Payment": {
      "properties": {
        "payment_id": {
          "title": "Payment Id",
          "type": "string"
        },
        "amount": {
          "$ref": "#/$defs/Money"
        },
        "payment_reference": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Payment Reference"
        },
        "recorded_by": {
          "title": "Recorded By",
          "type": "string"
        },
        "recorded_at": {
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "payment_id",
        "amount",
        "payment_reference",
        "recorded_by",
        "recorded_at"
      ],
      "title": "Payment",
      "type": "object"
    },
    "RequestCounts": {
      "properties": {
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "approved": {
          "title": "Approved",
          "type": "integer"
        },
        "rejected": {
          "title": "Rejected",
          "type": "integer"
        },
        "paid": {
          "title": "Paid",
          "type": "integer"
        }
      },
      "required": [
        "pending",
        "approved",
        "rejected",
        "paid"
      ],
      "title": "RequestCounts",
      "type": "object"
    }
  },
  "properties": {
    "request": {
      "$ref": "#/$defs/AssistanceRequest"
    },
    "fund": {
      "$ref": "#/$defs/FundSummary",
      "description": "The request's fund after this call"
    },
    "replayed": {
      "description": "True if this call repeated an already-applied action and changed nothing",
      "title": "Replayed",
      "type": "boolean"
    }
  },
  "required": [
    "request",
    "fund",
    "replayed"
  ],
  "title": "MutationResult",
  "type": "object"
}
```

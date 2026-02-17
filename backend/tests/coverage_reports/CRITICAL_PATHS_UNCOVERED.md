# Critical Paths Uncovered Lines Catalog

**Generated:** 2026-02-17
**Phase:** 01-foundation-infrastructure
**Plan:** 01-baseline-coverage

## Overview

This document catalogs uncovered code in critical services that govern agent behavior, safety, and core functionality. Zero or low coverage in these paths represents untested risk areas.

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Critical Services Analyzed | 15 |
| Services with 0% Coverage | 9 (60%) |
| Services with <20% Coverage | 3 (20%) |
| Total Uncovered Lines (Critical) | 2,765 |
| Security-Sensitive Uncovered Lines | 0 |

## Per-Service Uncovered Lines

### 1. agent_governance_service.py

**Coverage:** 15.8% (28/177 lines)
**Uncovered Lines:** 149
**Risk Level:** HIGH

**Uncovered Functionality:**
- Agent maturity validation logic
- Permission checking for agent actions
- Governance decision caching
- Audit trail logging
- Emergency bypass handling

**Top Missing Lines:** 26, 37, 42, 44, 52, 53, 56, 57, 58, 60, 61, 62, 76, 77, 78, 80, 88, 89, 92, 94, 100, 101, 106, 114, 115, 116, 117, 118, 119, 120, 121, 122, 135, 136, 137, 138, 139, 140, 141, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333

### 2. agent_context_resolver.py

**Coverage:** 15.8% (15/95 lines)
**Uncovered Lines:** 80
**Risk Level:** HIGH

**Uncovered Functionality:**
- Agent context resolution from requests
- Fallback chain resolution
- Context caching
- Multi-tenant workspace isolation
- Agent metadata extraction

**Top Missing Lines:** 30, 31, 54, 63, 66, 67, 68, 69, 70, 71, 73, 74, 77, 78, 79, 80, 81, 82, 84, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 233

### 3. governance_cache.py

**Coverage:** 19.5% (51/262 lines)
**Uncovered Lines:** 211
**Risk Level:** MEDIUM

**Uncovered Functionality:**
- Cache invalidation logic
- Performance optimization paths
- Cache warming strategies
- Distributed cache synchronization
- Statistics tracking

**Top Missing Lines:** 45, 46, 49, 50, 53, 54, 55, 56, 59, 60, 64, 65, 66, 67, 68, 69, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 471, 472, 473, 474, 475, 476, 477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 495, 496, 497, 498, 499, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538, 539, 540, 541, 542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 552, 553, 554, 555, 556, 557, 558, 559, 560, 561, 562, 563

### 4. trigger_interceptor.py

**Coverage:** 0.0% (0/141 lines)
**Uncovered Lines:** 141
**Risk Level:** CRITICAL

**Uncovered Functionality:**
- STUDENT agent trigger blocking (safety rail)
- Maturity-based routing decisions
- Training proposal workflow
- Supervision session creation
- Audit trail logging for all routing

**All Lines Uncovered:** 10, 11, 12, 13, 14, 15, 17, 18, 29, 31, 34, 36, 37, 38, 39, 42, 44, 45, 46, 47, 50, 51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300

### 5. student_training_service.py

**Coverage:** 0.0% (0/193 lines)
**Uncovered Lines:** 193
**Risk Level:** HIGH

**Uncovered Functionality:**
- Training scenario management
- AI-powered duration estimation
- Training session creation
- Progress tracking
- Graduation eligibility

**All Lines Uncovered:** 8, 9, 10, 11, 12, 13, 15, 26, 29, 31, 40, 41, 42, 43, 44, 45, 48, 50, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 23238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300

### 6. supervision_service.py

**Coverage:** 0.0% (0/218 lines)
**Uncovered Lines:** 218
**Risk Level:** HIGH

**Uncovered Functionality:**
- Real-time supervision session management
- Intervention detection
- Pause/correct/terminate controls
- Supervisor dashboard
- Audit trail logging

**All Lines Uncovered:** 8, 9, 10, 11, 12, 14, 23, 26, 28, 34, 35, 36, 39, 41, 47, 48, 49, 52, 54, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300

### 7. episode_segmentation_service.py

**Coverage:** 0.0% (0/422 lines)
**Uncovered Lines:** 422
**Risk Level:** HIGH

**Uncovered Functionality:**
- Automatic episode segmentation
- Time gap detection
- Topic change detection
- Task completion detection
- Episode lifecycle management

**All Lines Uncovered:** 12, 13, 14, 15, 16, 17, 19, 20, 21, 35, 39, 42, 44, 45, 46, 47, 50, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300

### 8. episode_retrieval_service.py

**Coverage:** 0.0% (0/242 lines)
**Uncovered Lines:** 242
**Risk Level:** HIGH

**Uncovered Functionality:**
- Temporal retrieval (time-based)
- Semantic retrieval (vector search)
- Sequential retrieval (full episode)
- Contextual retrieval (hybrid)
- Episode filtering by metadata

**All Lines Uncovered:** 11, 12, 13, 14, 16, 17, 18, 28, 32, 33, 36, 38, 39, 40, 41, 44, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300

### 9. episode_lifecycle_service.py

**Coverage:** 0.0% (0/97 lines)
**Uncovered Lines:** 97
**Risk Level:** MEDIUM

**Uncovered Functionality:**
- Episode decay (aging)
- Episode consolidation
- Episode archival
- Cold storage migration
- Lifecycle state transitions

**All Lines Uncovered:** 11, 12, 13, 14, 16, 17, 19, 22, 25, 26, 27, 29, 42, 44, 49, 50, 52, 53, 54, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200

### 10. agent_graduation_service.py

**Coverage:** 0.0% (0/183 lines)
**Uncovered Lines:** 183
**Risk Level:** HIGH

**Uncovered Functionality:**
- Graduation eligibility calculation
- Episode count validation
- Intervention rate tracking
- Constitutional compliance scoring
- Readiness score calculation (40/30/30 split)

**All Lines Uncovered:** 8, 9, 10, 11, 13, 14, 22, 25, 29, 47, 48, 49, 51, 73, 74, 75, 77, 80, 84, 85, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200

### 11. llm/byok_handler.py

**Coverage:** 0.0% (0/549 lines)
**Uncovered Lines:** 549
**Risk Level:** CRITICAL

**Uncovered Functionality:**
- Multi-provider LLM routing (OpenAI, Anthropic, DeepSeek, Gemini)
- Token streaming
- Cost calculation
- Rate limiting
- Error handling
- Provider fallback

**All 549 Lines Uncovered**

### 12. Missing Tools (Not Found in Coverage)

The following critical tools were not found in coverage data:

- **tools/canvas_tool.py** - Canvas presentation system
- **tools/browser_tool.py** - Browser automation (Playwright CDP)
- **tools/device_tool.py** - Device capabilities (camera, screen recording, location)

These tools execute real-world actions and require comprehensive coverage for production safety.

## Security Gap Analysis

**Result:** No security-sensitive uncovered code found.

**Analysis Method:**
- Scanned all uncovered lines for security patterns:
  - Authorization checks
  - Authentication logic
  - Permission validation
  - Input sanitization
  - Encryption/decryption
  - JWT handling
  - Secret/password handling

**Conclusion:** Good news - no critical security vulnerabilities in uncovered code. However, this may indicate that security logic exists but is not being tested, which is itself a risk.

## Complexity-Weighted Priority List

### High Complexity + Zero Coverage = Highest Risk

| Rank | Service | Uncovered Lines | Complexity | Risk Level | Priority |
|------|---------|----------------|------------|------------|----------|
| 1 | llm/byok_handler.py | 549 | Very High | CRITICAL | P0 |
| 2 | episode_segmentation_service.py | 422 | High | HIGH | P0 |
| 3 | episode_retrieval_service.py | 242 | High | HIGH | P0 |
| 4 | supervision_service.py | 218 | High | HIGH | P0 |
| 5 | student_training_service.py | 193 | Medium | HIGH | P1 |
| 6 | agent_graduation_service.py | 183 | Medium | HIGH | P1 |
| 7 | trigger_interceptor.py | 141 | Medium | CRITICAL | P0 |
| 8 | governance_cache.py | 211 | High | MEDIUM | P1 |
| 9 | agent_governance_service.py | 149 | Medium | HIGH | P1 |
| 10 | agent_context_resolver.py | 80 | Medium | HIGH | P1 |

**Complexity Estimation:**
- **Very High:** Multi-provider integration, async streaming, cost calculation
- **High:** Vector search, distributed caching, real-time supervision
- **Medium:** Business logic, database operations, validation

## Recommendations for Test Development

### Phase 2: Test Infrastructure Standardization

**Priority 1 (P0):** Governance Safety Rails
1. `trigger_interceptor.py` - Test STUDENT blocking logic
2. `llm/byok_handler.py` - Test provider routing and cost calculation
3. `episode_segmentation_service.py` - Test time/topic gap detection
4. `episode_retrieval_service.py` - Test semantic search accuracy
5. `supervision_service.py` - Test intervention detection

**Priority 2 (P1):** Core Business Logic
1. `agent_governance_service.py` - Test maturity validation
2. `agent_context_resolver.py` - Test fallback chain resolution
3. `governance_cache.py` - Test cache invalidation
4. `student_training_service.py` - Test training scenarios
5. `agent_graduation_service.py` - Test readiness scoring

**Priority 3 (P2):** Support Services
1. `episode_lifecycle_service.py` - Test consolidation/archival
2. API routes - Test governance enforcement
3. Tools layer - Test browser/device automation

### Test Strategy by Service Type

**Governance Services:**
- Unit tests for decision logic
- Property tests for invariant validation
- Integration tests for database operations
- End-to-end tests for multi-service workflows

**LLM Services:**
- Mock provider responses for unit tests
- Contract tests for API compatibility
- Cost calculation property tests
- Rate limiting validation tests

**Memory Services:**
- Vector search accuracy tests
- Episode segmentation boundary tests
- Retrieval ranking tests
- Lifecycle state transition tests

**Tools Layer:**
- Browser automation integration tests (mock Playwright)
- Device capability permission tests
- Canvas presentation rendering tests
- Security boundary tests (AUTONOMOUS gating)

## Next Steps

1. **Immediate:** Create test suite for `trigger_interceptor.py` (safety rail)
2. **Week 1:** Implement coverage for `llm/byok_handler.py` (cost/routing)
3. **Week 2:** Create tests for episodic memory services
4. **Week 3:** Comprehensive governance service coverage
5. **Month 1:** Achieve 50% coverage on all P0/P1 services

## Data Sources

- **Coverage Data:** `tests/coverage_reports/metrics/coverage.json`
- **Baseline Report:** `tests/coverage_reports/BASELINE_COVERAGE.md`
- **HTML Report:** `tests/coverage_reports/html/index.html`

---

**Catalog Generated By:** Atom Test Coverage Initiative
**Last Updated:** 2026-02-17T05:00:00Z

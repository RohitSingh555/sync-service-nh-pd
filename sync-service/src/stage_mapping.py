# Stage mapping for Pipedrive stages
# This file contains mappings between stage names and IDs for all pipelines

# Forward mapping: Stage name -> Stage ID
STAGE_NAME_TO_ID = {
    # Sales Pipeline (pipeline_id: 1)
    "Form Submitted": 1,
    "Call Booked": 3,
    "Considering": 4,
    "Onboarding": 38,
    
    # HA Candidates Pipeline (pipeline_id: 2)
    "Application Submitted": 13,
    "Applicant Reviewed": 12,
    "Contact Made": 46,
    "Interview Set": 11,
    "Considering": 79,  # Note: This conflicts with Sales pipeline "Considering"
    "Assessment Requested": 78,
    "Decision Pending": 58,
    "Offer Extended": 8,
    "Onboarding": 63,  # Note: This conflicts with Sales pipeline "Onboarding"
    
    # Staff Pipeline (pipeline_id: 3)
    "Onboard**": 17,
    "Schedule Assignments": 18,
    "Send STA**": 60,
    "Meal Plan**": 64,
    "Intro Period**": 20,
    "HAs Currently Working": 22,
    "CHEFS Currently Working": 65,
    "Pause/Sub": 55,
    
    # Clients Pipeline (pipeline_id: 4)
    "Signed & Paid": 40,
    "Staff Finalized": 50,
    "Trial Period": 56,
    "Active": 41,
    "Departing": 57,
    
    # CHEF Candidates Pipeline (pipeline_id: 5)
    "Application Submitted": 66,  # Note: This conflicts with HA Candidates
    "Applicant Reviewed": 67,     # Note: This conflicts with HA Candidates
    "Contact Made": 68,           # Note: This conflicts with HA Candidates
    "Interview Set": 69,          # Note: This conflicts with HA Candidates
    "Considering": 70,            # Note: This conflicts with Sales and HA Candidates
    "Audition Requested": 75,
    "Audition Scheduled": 71,
    "Decision Pending": 80,       # Note: This conflicts with HA Candidates
    "Offer Extended": 72,         # Note: This conflicts with HA Candidates
    "Onboarding": 73,             # Note: This conflicts with Sales and HA Candidates
}

# Reverse mapping: Stage ID -> Stage name
STAGE_ID_TO_NAME = {
    1: "Form Submitted",
    3: "Call Booked",
    4: "Considering",
    38: "Onboarding",
    13: "Application Submitted",
    12: "Applicant Reviewed",
    46: "Contact Made",
    11: "Interview Set",
    79: "Considering",
    78: "Assessment Requested",
    58: "Decision Pending",
    8: "Offer Extended",
    63: "Onboarding",
    17: "Onboard**",
    18: "Schedule Assignments",
    60: "Send STA**",
    64: "Meal Plan**",
    20: "Intro Period**",
    22: "HAs Currently Working",
    65: "CHEFS Currently Working",
    55: "Pause/Sub",
    40: "Signed & Paid",
    50: "Staff Finalized",
    56: "Trial Period",
    41: "Active",
    57: "Departing",
    66: "Application Submitted",
    67: "Applicant Reviewed",
    68: "Contact Made",
    69: "Interview Set",
    70: "Considering",
    75: "Audition Requested",
    71: "Audition Scheduled",
    80: "Decision Pending",
    72: "Offer Extended",
    73: "Onboarding",
}

# Pipeline mapping for context
PIPELINE_ID_TO_NAME = {
    1: "Sales",
    2: "HA Candidates",
    3: "Staff",
    4: "Clients",
    5: "CHEF Candidates",
}

# Pipeline name to ID mapping
PIPELINE_NAME_TO_ID = {
    "Sales": 1,
    "HA Candidates": 2,
    "Staff": 3,
    "Clients": 4,
    "CHEF Candidates": 5,
}

def get_stage_id(stage_name: str) -> int:
    """Get stage ID from stage name"""
    return STAGE_NAME_TO_ID.get(stage_name)

def get_stage_name(stage_id: int) -> str:
    """Get stage name from stage ID"""
    return STAGE_ID_TO_NAME.get(stage_id)

def get_pipeline_id(pipeline_name: str) -> int:
    """Get pipeline ID from pipeline name"""
    return PIPELINE_NAME_TO_ID.get(pipeline_name)

def get_pipeline_name(pipeline_id: int) -> str:
    """Get pipeline name from pipeline ID"""
    return PIPELINE_ID_TO_NAME.get(pipeline_id) 
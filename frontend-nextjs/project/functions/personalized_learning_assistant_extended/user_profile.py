def create_user_profile(coursera_data, udemy_data, edx_data, pocket_data, instapaper_data, notion_data):
    """
    Creates a user profile based on data from different sources.

    Args:
        coursera_data: A dictionary containing the Coursera data.
        udemy_data: A dictionary containing the Udemy data.
        edx_data: A dictionary containing the edX data.
        pocket_data: A dictionary containing the Pocket data.
        instapaper_data: A dictionary containing the Instapaper data.
        notion_data: A dictionary containing the Notion data.

    Returns:
        A dictionary representing the user's profile.
    """
    interests = set()
    knowledge = set()

    # Process Coursera data
    for course in coursera_data["enrolled_courses"]:
        interests.add(course["name"])
        if course["progress"] > 0.8:
            knowledge.add(course["name"])

    # Process Udemy data
    for course in udemy_data["enrolled_courses"]:
        interests.add(course["name"])
        if course["progress"] > 0.8:
            knowledge.add(course["name"])

    # Process edX data
    for course in edx_data["enrolled_courses"]:
        interests.add(course["name"])
        if course["progress"] > 0.8:
            knowledge.add(course["name"])

    # Process Pocket data
    for article in pocket_data["unread_articles"]:
        for tag in article["tags"]:
            interests.add(tag)

    # Process Instapaper data
    for article in instapaper_data["unread_articles"]:
        for tag in article["tags"]:
            interests.add(tag)

    # Process Notion data
    for page in notion_data["pages"]:
        if "Tags" in page["properties"] and "multi_select" in page["properties"]["Tags"]:
            for tag in page["properties"]["Tags"]["multi_select"]:
                interests.add(tag["name"])

    return {
        "interests": list(interests),
        "knowledge": list(knowledge),
    }

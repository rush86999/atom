import React, {
    useState,
    useEffect,
  } from 'react'
  import {
    FlatList,
    Pressable,
} from 'react-native'
import TextField from '@components/TextField'
import { IoIosClose } from "react-icons/io"
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import Button from '@components/Button'
import { palette } from '@lib/theme/theme'
import {
    CategoryType
} from '@lib/dataTypes/CategoryType'
import {
    addCategoryToUser,
    listUserCategories,
    removeCategory,
    removeEventConnectionsForCategory,
} from '@lib/Category/CategoryHelper'
import { ApolloClient, NormalizedCacheObject } from '@apollo/client'

type Props = {
    sub: string,
    client: ApolloClient<NormalizedCacheObject>,
}
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
import Session from 'supertokens-node/recipe/session'

export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig())
  let session
  try {
    session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return []
      },
    })
  } catch (err: any) {
    if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } }
    } else if (err.type === Session.Error.UNAUTHORISED) {
      // this will force the frontend to try and refresh which will fail
      // clearing all cookies and redirecting the user to the login screen.
      return { props: { fromSupertokens: 'needs-refresh' } }
    }
    throw err
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: '/User/Login/UserLogin',
        permanent: false,
      },
    }
  }

  return {
    props: {
      sub: session.getUserId(),
    }
  }
}

function UserAddTags(props: Props) {
    const [categories, setCategories] = useState<CategoryType[]>([])
    const [name, setName] = useState<string>('')

    const userId = props?.sub
    const client = props?.client


    // get old categories
    useEffect(() => {
        (async () => {
            try {
                const categories = await listUserCategories(client, userId)
                setCategories(categories)
            } catch (error) {
                console.log(error)
            }
        })()
    }, [client, userId])

    // add new category to categories
    const addCategory = async () => {
        try {
            // validate
            if (name.length === 0) {
                return
            }
            const newCategory = await addCategoryToUser(client, userId, name)
            setCategories([...categories, newCategory])
            setName('')
        } catch (error) {
            console.log(error)
        }
    }

    // remove category from categories
    const removeCategoryForUser = async (categoryId: string) => {
        try {
            setCategories(categories.filter(category => category.id !== categoryId))
            await removeCategory(client, categoryId)
            await removeEventConnectionsForCategory(client, categoryId)
        } catch (error) {
            console.log(error)
        }
    }

    return (
        <Box flex={1} justifyContent="space-around" alignItems="center" style={{ width: '100%' }}>
            <Box flex={4} pt={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="center" style={{ width: '100%' }}>
                <Box justifyContent="center" alignItems="center" style={{ width: '100%' }}>
                <Box mb="m" width="80%" alignItems="center">
                    <Text textAlign="center">
                        Add tags (or categories) to help organize your schedule and assist Atomic in understanding your priorities. For example, you could create tags like 'Work', 'Personal', 'Urgent', or 'Exercise'.
                    </Text>
                </Box>
                <FlatList
                    data={categories}
                    renderItem={({ item, index }) => (
                        <Box p={{ phone: 'xs', tablet: 's' }} style={{ width: '100%' }} alignItems="center" justifyContent="center">
                            <Box style={{ width: '50%' }} flexDirection="row" justifyContent="space-between">
                                <Text variant="optionHeader">
                                    {item.name}
                                </Text>
                                <Pressable hitSlop={15} onPress={() => removeCategoryForUser(categories?.[index]?.id)}>
                                    <IoIosClose size="3em" color={palette.red} />
                                </Pressable>
                            </Box>
                        </Box>
                    )}
                    keyExtractor={(item) => item.id}
                />
                </Box>
            </Box>
            <Box flex={1}>
                <Box p={{ phone: 'xs', tablet: 's' }}>

                    <TextField
                        onChange={(e: { target: { value: string } }) => setName(e?.target?.value)}
                        value={name}
                        placeholder="Get together"
                        label="Tag"
                        style={{ width: '60%' }}
                    />
                    
                </Box>
            </Box>
            <Box flex={1} p={{ phone: 'xs', tablet: 's' }} justifyContent="center" alignItems="center">
                <Button onClick={addCategory}>
                    Add New Tag
                </Button>
            </Box>
        </Box>
    )
}

export default UserAddTags



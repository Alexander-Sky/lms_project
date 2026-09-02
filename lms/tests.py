from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from lms.models import Course, Lesson, Subscription
from users.models import User

YOUTUBE_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
FOREIGN_URL = 'https://vimeo.com/123456'


class LmsBaseTestCase(APITestCase):
    """Общая подготовка данных: владелец, посторонний, модератор, курс и урок."""

    def setUp(self):
        self.owner = User.objects.create(email='owner@test.ru')
        self.stranger = User.objects.create(email='stranger@test.ru')
        self.moder = User.objects.create(email='moder@test.ru')

        self.moderators = Group.objects.create(name='Модераторы')
        self.moder.groups.add(self.moderators)

        self.course = Course.objects.create(
            name='Тестовый курс',
            description='Описание курса',
            owner=self.owner,
        )
        self.lesson = Lesson.objects.create(
            name='Тестовый урок',
            description='Описание урока',
            course=self.course,
            video_url=YOUTUBE_URL,
            owner=self.owner,
        )


class LessonCreateTestCase(LmsBaseTestCase):
    """Создание урока."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-create')
        self.payload = {
            'name': 'Новый урок',
            'description': 'Описание',
            'course': self.course.pk,
            'video_url': YOUTUBE_URL,
        }

    def test_anonymous_cannot_create(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_creates_lesson_and_becomes_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['owner'], self.owner.pk)
        self.assertEqual(Lesson.objects.count(), 2)

    def test_moderator_cannot_create(self):
        self.client.force_authenticate(user=self.moder)
        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Lesson.objects.count(), 1)


class LessonRetrieveTestCase(LmsBaseTestCase):
    """Просмотр урока."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-detail', args=(self.lesson.pk,))

    def test_owner_sees_lesson(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['name'], self.lesson.name)

    def test_moderator_sees_lesson(self):
        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)

    def test_stranger_cannot_see_lesson(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)


class LessonListTestCase(LmsBaseTestCase):
    """Список уроков и пагинация."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-list')
        Lesson.objects.create(name='Чужой урок', course=self.course, owner=self.stranger)

    def test_owner_sees_only_own_lessons(self):
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(self.url).json()

        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], self.lesson.name)

    def test_moderator_sees_all_lessons(self):
        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(self.url).json()['count'], 2)

    def test_response_is_paginated(self):
        self.client.force_authenticate(user=self.moder)
        data = self.client.get(self.url).json()

        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertIn('previous', data)
        self.assertIn('results', data)

    def test_page_size_query_param(self):
        self.client.force_authenticate(user=self.moder)
        data = self.client.get(self.url, {'page_size': 1}).json()

        self.assertEqual(len(data['results']), 1)
        self.assertIsNotNone(data['next'])


class LessonUpdateTestCase(LmsBaseTestCase):
    """Редактирование урока."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-update', args=(self.lesson.pk,))

    def test_owner_can_update(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(self.url, {'name': 'Обновлённый урок'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, 'Обновлённый урок')

    def test_moderator_can_update(self):
        self.client.force_authenticate(user=self.moder)
        response = self.client.patch(self.url, {'name': 'Правка модератора'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stranger_cannot_update(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.patch(self.url, {'name': 'Взлом'})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, 'Тестовый урок')


class LessonDestroyTestCase(LmsBaseTestCase):
    """Удаление урока."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-delete', args=(self.lesson.pk,))

    def test_owner_can_delete(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Lesson.objects.count(), 0)

    def test_moderator_cannot_delete(self):
        self.client.force_authenticate(user=self.moder)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Lesson.objects.count(), 1)

    def test_stranger_cannot_delete(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN)


class LinksValidatorTestCase(LmsBaseTestCase):
    """Валидатор ссылок: к записи допускается только youtube.com."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:lesson-create')
        self.client.force_authenticate(user=self.owner)

    def test_youtube_link_is_allowed(self):
        response = self.client.post(self.url, {
            'name': 'Урок с youtube',
            'course': self.course.pk,
            'video_url': YOUTUBE_URL,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_short_youtube_link_is_allowed(self):
        response = self.client.post(self.url, {
            'name': 'Урок с youtu.be',
            'course': self.course.pk,
            'video_url': 'https://youtu.be/dQw4w9WgXcQ',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_foreign_link_is_rejected(self):
        response = self.client.post(self.url, {
            'name': 'Урок со сторонней ссылкой',
            'course': self.course.pk,
            'video_url': FOREIGN_URL,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('youtube.com', str(response.json()))
        self.assertEqual(Lesson.objects.count(), 1)

    def test_foreign_link_in_description_is_rejected(self):
        response = self.client.post(self.url, {
            'name': 'Урок',
            'course': self.course.pk,
            'description': f'Подробнее тут: {FOREIGN_URL}',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lookalike_domain_is_rejected(self):
        """youtube.com.evil.ru не должен пройти как youtube.com."""
        response = self.client.post(self.url, {
            'name': 'Урок',
            'course': self.course.pk,
            'video_url': 'https://youtube.com.evil.ru/watch',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_course_description_is_validated(self):
        response = self.client.post(reverse('lms:course-list'), {
            'name': 'Курс со ссылкой',
            'description': f'Материалы: {FOREIGN_URL}',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SubscriptionTestCase(LmsBaseTestCase):
    """Подписка на обновления курса."""

    def setUp(self):
        super().setUp()
        self.url = reverse('lms:subscription')
        self.client.force_authenticate(user=self.owner)

    def test_anonymous_cannot_subscribe(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {'course_id': self.course.pk})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscription_is_created(self):
        response = self.client.post(self.url, {'course_id': self.course.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['message'], 'подписка добавлена')
        self.assertTrue(Subscription.objects.filter(user=self.owner, course=self.course).exists())

    def test_subscription_is_deleted_on_second_call(self):
        self.client.post(self.url, {'course_id': self.course.pk})
        response = self.client.post(self.url, {'course_id': self.course.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['message'], 'подписка удалена')
        self.assertEqual(Subscription.objects.count(), 0)

    def test_missing_course_id_returns_400(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_course_returns_404(self):
        response = self.client.post(self.url, {'course_id': 9999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_is_subscribed_flag_in_course(self):
        url = reverse('lms:course-detail', args=(self.course.pk,))

        self.assertFalse(self.client.get(url).json()['is_subscribed'])

        self.client.post(self.url, {'course_id': self.course.pk})
        self.assertTrue(self.client.get(url).json()['is_subscribed'])

    def test_subscription_is_personal(self):
        """Подписка одного пользователя не видна другому."""
        self.client.post(self.url, {'course_id': self.course.pk})

        self.client.force_authenticate(user=self.moder)
        url = reverse('lms:course-detail', args=(self.course.pk,))
        self.assertFalse(self.client.get(url).json()['is_subscribed'])


class CourseTestCase(LmsBaseTestCase):
    """CRUD курсов и права по action."""

    def test_user_creates_course_and_becomes_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(reverse('lms:course-list'), {'name': 'Ещё курс'})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['owner'], self.owner.pk)

    def test_moderator_cannot_create_course(self):
        self.client.force_authenticate(user=self.moder)
        response = self.client.post(reverse('lms:course-list'), {'name': 'Курс модератора'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_cannot_delete_course(self):
        self.client.force_authenticate(user=self.moder)
        url = reverse('lms:course-detail', args=(self.course.pk,))

        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Course.objects.count(), 1)

    def test_owner_can_delete_course(self):
        self.lesson.delete()
        self.client.force_authenticate(user=self.owner)
        url = reverse('lms:course-detail', args=(self.course.pk,))

        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)

    def test_course_list_is_paginated_and_filtered_by_owner(self):
        Course.objects.create(name='Чужой курс', owner=self.stranger)

        self.client.force_authenticate(user=self.owner)
        data = self.client.get(reverse('lms:course-list')).json()
        self.assertEqual(data['count'], 1)

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(reverse('lms:course-list')).json()['count'], 2)

    def test_lessons_count_and_nested_lessons(self):
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(reverse('lms:course-detail', args=(self.course.pk,))).json()

        self.assertEqual(data['lessons_count'], 1)
        self.assertEqual(len(data['lessons']), 1)


class LmsModelTestCase(LmsBaseTestCase):
    """Строковые представления моделей."""

    def test_course_str(self):
        self.assertEqual(str(self.course), 'Тестовый курс')

    def test_lesson_str(self):
        self.assertEqual(str(self.lesson), 'Тестовый урок')

    def test_subscription_str(self):
        subscription = Subscription.objects.create(user=self.owner, course=self.course)

        self.assertIn(self.owner.email, str(subscription))
        self.assertIn(self.course.name, str(subscription))

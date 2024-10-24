import json
import sqlite3
import hashlib
from typing import List
# from models import Post, Partner, Contact
import os
from sqlalchemy import text

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from models import *
from sqlalchemy import inspect, func, create_engine
from sqlalchemy.exc import NoResultFound
from config import DB


class Database():
    def __init__(self, database_url: str):
        """Инициализация БД"""
        engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=engine)
        # создаем все таблицы из моделей в БД
        Base.metadata.create_all(bind=engine)
        try:
            connection = engine.connect()
            print("Соединение с базой данных установлено")
            connection.close()
        except Exception as e:
            print(f"Ошибка соединения с базой данных: {e}")

    def get_session(self):
        with self.session_factory() as session:
            return session

    def get_contacts_info(self, db: Session):
        """
        Получение информации по контактам
        :param db:
        :return:
        """
        contacts = db.query(Contact).all()
        return [{k: v for k, v in contact.__dict__.items() if k != '_sa_instance_state'} for contact in contacts]

    def create_user(self, db: Session, username: str, password: str):
        """
        Создание пользователя
        :param db:
        :param username:
        :param password:
        :return:
        """
        # Хеширование пароля
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        print(hashed_password)
        # Создание нового пользователя
        new_user = User(username=username, password=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    def get_all_tables(self, db: Session):
        """
        Получаем названия всех таблиц
        :param db:
        :return:
        """
        inspector = inspect(db.get_bind())  # Получаем объект инспектора
        return inspector.get_table_names()  # Возвращаем список имен всех таблиц

    def get_news(self, db: Session, tag=None, sort_by_date_descending=False):
        """
        Получаем все статьи из БД
        :param db:
        :param tag:
        :param sort_by_date_descending:
        :return:
        """
        query = db.query(News)

        if tag:
            query = query.filter(News.tag == tag)  # Добавляем фильтрацию по тегу

        if sort_by_date_descending:
            query = query.order_by(News.updated.desc())  # Сортировка по дате в обратном порядке

        news_items = query.all()
        return [{k: v for k, v in news_item.__dict__.items() if k != '_sa_instance_state'} for news_item in news_items]

    def get_main_article(self, db: Session):
        """
        Получаем главную статью
        :param db:
        :return:
        """
        # Вытаскиваем все новости, где id совпадает с id в таблице main_article
        main_articles = db.query(News).join(MainArticle, News.id == MainArticle.id).all()
        return [{k: v for k, v in main_article.__dict__.items() if k != '_sa_instance_state'} for main_article in
                main_articles]

    def get_news_by_id(self, db: Session, *args):
        """
        Получаем новости по их id
        :param db:
        :param args:
        :return:
        """
        news_items = db.query(News).filter(News.id.in_(args)).all()  # Фильтрация по списку id
        print([{k: v for k, v in news_item.__dict__.items() if k != '_sa_instance_state'} for news_item in news_items])
        return [{k: v for k, v in news_item.__dict__.items() if k != '_sa_instance_state'} for news_item in news_items]

    def get_partners(self, db: Session):
        """
        Получаем данные по партнерам
        :param db: 
        :return: 
        """
        partners = db.query(Partner).all()  # Получаем все записи из таблицы partners
        return [{k: v for k, v in partner.__dict__.items() if k != '_sa_instance_state'} for partner in partners]

    def make_main(self, db: Session, new_id: int):
        """
        Обновляет поле id в таблице main_article. Задает главную новость
        param db: Сессия базы данных.
        param new_id: Новое значение для поля id.
        :return: None
        """
        try:
            # Выполнение обновления
            db.query(MainArticle).update({"id": new_id})
            db.commit()
        except Exception as e:
            db.rollback()  # Откат изменений в случае ошибки
            print(f"Ошибка обновления: {e}")

    def get_model_by_table_name(self, table_name: str):
        """Получение модели по названию таблицы"""
        for cls in Base.registry.mappers:
            if cls.class_.__tablename__ == table_name:
                return cls.class_
        raise ValueError(f"Модель для таблицы '{table_name}' не найдена.")

    def get_next_id(self, session: Session, table_name: str):
        """Получение максимального ID и его увеличение на 1 для таблицы"""
        model = self.get_model_by_table_name(table_name)
        max_id = session.query(
            func.max(model.id)).scalar()  # Используем функцию func.max для получения максимального ID
        next_id = (max_id or 0) + 1  # Если max_id None (например, если таблица пуста), устанавливаем 0
        return next_id

    def insert_data(self, session: Session, table_name: str, data: dict):
        """
        Вставка данных в таблицу БД
        :param session:
        :param table_name:
        :param data:
        :return:
        """
        model = self.get_model_by_table_name(table_name)

        # Создаем экземпляр модели с переданными данными
        instance = model(**data)

        # Добавляем и коммитим изменения
        session.add(instance)
        session.commit()

        # Обновляем экземпляр сессией, чтобы получить ID или другие обновленные поля
        session.refresh(instance)

        return instance

    def get_model_columns(self, table_name: str):
        """
        Получение списка колонок для модели по названию таблицы
        :param table_name:
        :return:
        """
        model = self.get_model_by_table_name(table_name)
        return [column.name for column in model.__table__.columns]

    def get_user_by_username(self, db: Session, username: str):
        """
        Получение пользователя по username.
        :param db: Сессия базы данных.
        :param username: Имя пользователя для поиска.
        :return: Объект пользователя или None, если пользователь не найден.
        """
        try:
            # Поиск пользователя по имени пользователя
            user = db.query(User).filter(User.username == username).one_or_none()
            return user.__dict__
        except NoResultFound:
            return None
        except Exception as e:
            print(f"Ошибка при получении пользователя: {e}")
            return None

    def get_data_admin_panel(self, db: Session, table: str, search_query: str, sort: str, order: str, per_page: int,
                             offset: int):
        """
        Получение данных из таблицы с учетом поиска, сортировки и постраничного вывода.
        :param db: Сессия базы данных.
        :param table: Название таблицы.
        :param search_query: Запрос для поиска.
        :param sort: Поле для сортировки.
        :param order: Направление сортировки (ASC или DESC).
        :param per_page: Количество записей на странице.
        :param offset: Смещение для постраничного вывода.
        :return: Общее количество записей и данные.
        """
        order_clause = text(f"{sort} {order}")

        model = self.get_model_by_table_name(table)
        column_names = [column.name for column in model.__table__.columns]
        total = db.query(func.count()).select_from(model).scalar()
        if search_query:
            total = db.query(func.count()).filter(model.title.like(f'%{search_query}%')).scalar()
            data = db.query(model).filter(model.title.like(f'%{search_query}%')).order_by(order_clause).limit(
                per_page).offset(offset).all()
        else:
            if table == "news":
                data = db.query(model).order_by(order_clause).limit(per_page).offset(offset).all()
                main_article = db.query(model.id).filter(model.id.in_(db.query(MainArticle.id))).scalar()

                return [{k: getattr(article, k) for k in column_names} for article in data], total, main_article
            else:
                data = db.query(model).all()

        return [{k: getattr(article, k) for k in column_names} for article in data], total, None

    def delete_record(self, db: Session, table_name: str, record_id: int):
        """
        Удаляет запись из указанной таблицы по ID.
        :param db: Сессия базы данных.
        :param table_name: Название таблицы для удаления записи.
        :param record_id: ID записи, которую нужно удалить.
        """
        try:
            model = self.get_model_by_table_name(table_name)

            record = db.query(model).filter(model.id == record_id).first()
            if record is None:
                raise NoResultFound(f"Запись с ID {record_id} не найдена в таблице {table_name}")

            db.delete(record)
            db.commit()
            print(f"Запись с ID {record_id} удалена из таблицы {table_name}")

        except Exception as e:
            print(f"Ошибка при удалении записи: {e}")

    def update_record(self, db: Session, table_name: str, record_id: int, data: dict):
        """
        Обновляет запись в указанной таблице по ID.
        :param db: Сессия базы данных.
        :param table_name: Название таблицы для обновления записи.
        :param record_id: ID записи, которую нужно обновить.
        :param data: Словарь с данными для обновления.
        """
        try:
            model = self.get_model_by_table_name(table_name)

            record = db.query(model).filter(model.id == record_id).first()
            if record is None:
                raise NoResultFound(f"Запись с ID {record_id} не найдена в таблице {table_name}")

            for key, value in data.items():
                setattr(record, key, value)

            db.commit()
            print(f"Запись с ID {record_id}  обновлена в таблице {table_name}")

        except Exception as e:
            print(f"Ошибка при обновлении записи: {e}")

    def get_record_by_id(self, db: Session, table_name: str, record_id: int):
        """Получает запись из указанной таблицы по ID.

        :param db: Сессия базы данных.
        :param table_name: Название таблицы для получения записи.
        :param record_id: ID записи для получения.
        :return: Найденная запись или None, если запись не найдена.
        """
        try:
            # Получаем модель на основе имени таблицы
            model = self.get_model_by_table_name(table_name)
            column_names = [column.name for column in model.__table__.columns]
            # Находим запись по ID
            data = db.query(model).filter(model.id == record_id).first()
            if data is None:
                raise NoResultFound(f"Запись с ID {record_id} не найдена в таблице {table_name}")
            return {k: data.__dict__[k] for k in column_names}

        except Exception as e:
            print(f"Ошибка при получении записи: {e}")
            return None

    def get_latest_news_titles(self, db: Session, limit: int = 100):
        """Получает последние заголовки новостей.

        :param db: Сессия базы данных.
        :param limit: Количество заголовков для выборки.
        :return: DataFrame с заголовками новостей.
        """
        news = db.query(News.id, News.title).order_by(News.updated.desc()).limit(limit).all()
        return news


DB.create_database()
database = Database(DB.get_path())
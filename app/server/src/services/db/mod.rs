//! 数据库模块
//!
//! 提供视频数据的数据库管理功能，包括连接管理、数据访问、目录同步等。

pub mod connection;
pub mod schema;
pub mod sync;
pub mod tree;
pub mod video_dao;

pub use connection::VideoDbManager;
pub use sync::DirectorySync;
pub use tree::TreeBuilder;
pub use video_dao::VideoDao;

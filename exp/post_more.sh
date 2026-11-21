for r in e5b_long:1 e5l_s13:0; do nohup bash post.sh ${r%%:*} ${r##*:} > ../logs/post_${r%%:*}.log 2>&1 & done

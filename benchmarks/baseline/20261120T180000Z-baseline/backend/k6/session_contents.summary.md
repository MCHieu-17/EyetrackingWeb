# k6 summary

scenario: session_contents

- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- iterations: count=230.000, rate=22.906
- vus: min=5.000, max=5.000
- http_req_sending: p(95)=0.062, p(99)=0.082, avg=0.037, min=0.005, med=0.039, max=0.101, p(90)=0.052
- http_req_receiving: min=0.023, med=0.076, max=1.353, p(90)=0.268, p(95)=0.337, p(99)=0.755, avg=0.131
- http_req_blocked: p(95)=0.021, p(99)=0.120, avg=0.013, min=0.002, med=0.010, max=0.125, p(90)=0.013
- http_req_duration: p(90)=24.850, p(95)=34.787, p(99)=43.503, avg=17.139, min=7.243, med=14.552, max=51.485
- http_req_duration{expected_response:true}: avg=17.139, min=7.243, med=14.552, max=51.485, p(90)=24.850, p(95)=34.787, p(99)=43.503
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.086, avg=0.002, min=0.000, med=0.000, max=0.092
- http_req_failed: rate=0.000
- http_req_waiting: avg=16.970, min=7.186, med=14.418, max=51.378, p(90)=24.624, p(95)=34.124, p(99)=43.329

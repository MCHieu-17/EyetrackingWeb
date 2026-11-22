# k6 summary

scenario: lesson_contents

- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.078, avg=0.002, min=0.000, med=0.000, max=0.084
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_sending: avg=0.039, min=0.008, med=0.039, max=0.210, p(90)=0.051, p(95)=0.058, p(99)=0.096
- http_req_blocked: avg=0.013, min=0.003, med=0.011, max=0.114, p(90)=0.014, p(95)=0.020, p(99)=0.112
- iterations: rate=23.354, count=237.000
- http_req_receiving: max=0.416, p(90)=0.194, p(95)=0.237, p(99)=0.306, avg=0.102, min=0.011, med=0.083
- http_req_duration{expected_response:true}: med=13.400, max=27.737, p(90)=18.842, p(95)=19.729, p(99)=22.789, avg=12.524, min=3.022
- http_req_waiting: p(99)=22.645, avg=12.383, min=2.971, med=13.139, max=27.648, p(90)=18.723, p(95)=19.601
- http_req_duration: p(90)=18.842, p(95)=19.729, p(99)=22.789, avg=12.524, min=3.022, med=13.400, max=27.737
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000

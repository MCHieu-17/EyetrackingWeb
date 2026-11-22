# k6 summary

scenario: course_visits

- http_req_failed: rate=0.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: min=0.010, med=0.011, max=0.767, p(90)=0.014, p(95)=0.052, p(99)=0.624, avg=0.049
- http_req_connecting: max=0.672, p(90)=0.000, p(95)=0.034, p(99)=0.545, avg=0.034, min=0.000, med=0.000
- http_req_receiving: med=0.230, max=0.415, p(90)=0.311, p(95)=0.405, p(99)=0.413, avg=0.236, min=0.104
- http_req_waiting: avg=41.051, min=18.114, med=42.175, max=61.485, p(90)=44.488, p(95)=47.347, p(99)=58.657
- iterations: count=20.000, rate=4.123
- http_req_duration: p(95)=47.791, p(99)=58.967, avg=41.332, min=18.268, med=42.434, max=61.761, p(90)=44.785
- http_req_duration{expected_response:true}: avg=41.332, min=18.268, med=42.434, max=61.761, p(90)=44.785, p(95)=47.791, p(99)=58.967
- vus: min=1.000, max=1.000
- http_req_sending: min=0.038, med=0.043, max=0.082, p(90)=0.053, p(95)=0.058, p(99)=0.077, avg=0.045
